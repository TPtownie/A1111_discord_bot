import aiohttp
import asyncio
import base64
import io
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from PIL import Image
import os

from .models import *

class A1111Interface:
    def __init__(self, base_url: str = "http://127.0.0.1:7860"):
        self.base_url = base_url
        self.api_url = f"{base_url}/sdapi/v1"
        self.job_queue: Dict[str, Dict] = {}
        self.job_results: Dict[str, Dict] = {}
        
    async def check_status(self) -> Dict[str, Any]:
        """Check if A1111 is running and get basic info"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/options") as response:
                    if response.status == 200:
                        return {"status": "online", "webui_version": "available"}
                    else:
                        return {"status": "error", "code": response.status}
        except Exception as e:
            return {"status": "offline", "error": str(e)}
    
    async def get_models(self) -> Dict[str, List[str]]:
        """Get all available models from A1111"""
        try:
            async with aiohttp.ClientSession() as session:
                # Get checkpoints
                async with session.get(f"{self.api_url}/sd-models") as response:
                    checkpoints_data = await response.json()
                    checkpoints = [model["model_name"] for model in checkpoints_data]
                
                # Get VAEs
                try:
                    async with session.get(f"{self.api_url}/sd-vae") as response:
                        vae_data = await response.json()
                        vaes = [vae["model_name"] for vae in vae_data]
                except:
                    vaes = ["Automatic", "None"]
                
                # Get samplers
                async with session.get(f"{self.api_url}/samplers") as response:
                    sampler_data = await response.json()
                    samplers = [sampler["name"] for sampler in sampler_data]
                
                # Get upscalers
                async with session.get(f"{self.api_url}/upscalers") as response:
                    upscaler_data = await response.json()
                    upscalers = [upscaler["name"] for upscaler in upscaler_data]
                
                return {
                    "checkpoints": checkpoints,
                    "vaes": vaes,
                    "samplers": samplers,
                    "upscalers": upscalers
                }
        except Exception as e:
            raise Exception(f"Failed to get models: {str(e)}")
    
    async def get_loras(self) -> List[Dict]:
        """Get LoRA information from A1111"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/loras") as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return []
        except:
            return []
    
    async def get_controlnet_models(self) -> List[str]:
        """Get available ControlNet models"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/controlnet/model_list") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("model_list", [])
                    return []
        except:
            return []
    
    async def build_txt2img_payload(self, request: Txt2ImgRequest, session: UserSession) -> Dict:
        """Build txt2img payload with session data"""
        # Apply LoRAs from session
        lora_prompt = self._build_lora_prompt(session.active_loras)
        full_prompt = f"{request.prompt} {lora_prompt}".strip()
        
        payload = {
            "prompt": full_prompt,
            "negative_prompt": request.negative_prompt,
            "sampler_name": request.sampler_name,
            "steps": request.steps,
            "cfg_scale": request.cfg_scale,
            "width": request.width,
            "height": request.height,
            "batch_count": request.batch_count,
            "batch_size": request.batch_size,
            "seed": request.seed,
            "enable_hr": request.enable_hr,
            "hr_scale": request.hr_scale,
            "denoising_strength": request.denoising_strength,
        }
        
        # Add model settings
        override_settings = {}
        if request.checkpoint:
            override_settings["sd_model_checkpoint"] = request.checkpoint
        if request.vae:
            override_settings["sd_vae"] = request.vae
        
        if override_settings:
            payload["override_settings"] = override_settings
            payload["override_settings_restore_afterwards"] = True
        
        # Add HR settings
        if request.enable_hr and request.hr_upscaler:
            payload["hr_upscaler"] = request.hr_upscaler
            payload["hr_second_pass_steps"] = request.hr_second_pass_steps
        
        # Add custom settings from session
        payload.update(session.custom_settings)
        
        return payload
    
    async def build_img2img_payload(self, request: Img2ImgRequest, session: UserSession, image_file) -> Dict:
        """Build img2img payload with session data"""
        # Process uploaded image
        image_data = await self._process_uploaded_image(image_file)
        
        # Build base payload
        payload = await self.build_txt2img_payload(request, session)
        payload.update({
            "init_images": [image_data],
            "resize_mode": request.resize_mode,
            "denoising_strength": request.denoising_strength,
            "inpaint_full_res": request.inpaint_full_res,
            "inpaint_full_res_padding": request.inpaint_full_res_padding,
            "inpainting_mask_invert": request.inpainting_mask_invert,
        })
        
        return payload
    
    async def build_controlnet_payload(self, request: ControlNetRequest, session: UserSession, 
                                     image_file, mask_file=None) -> Dict:
        """Build ControlNet payload with session data"""
        # Process uploaded images
        control_image = await self._process_uploaded_image(image_file)
        
        # Build ControlNet units
        controlnet_units = []
        for i, unit_config in enumerate(request.controlnet_units):
            unit = {
                "enabled": unit_config.enabled,
                "model": unit_config.model,
                "weight": unit_config.weight,
                "guidance_start": unit_config.guidance_start,
                "guidance_end": unit_config.guidance_end,
                "processor_res": unit_config.processor_res,
                "threshold_a": unit_config.threshold_a,
                "threshold_b": unit_config.threshold_b,
                "control_mode": unit_config.control_mode,
                "pixel_perfect": unit_config.pixel_perfect,
            }
            
            # Add image to first unit or if multiple images provided
            if i == 0:
                unit["input_image"] = control_image
            
            if unit_config.preprocessor:
                unit["module"] = unit_config.preprocessor
            
            controlnet_units.append(unit)
        
        # Build base payload
        payload = await self.build_txt2img_payload(request, session)
        
        # Add ControlNet configuration
        payload["alwayson_scripts"] = payload.get("alwayson_scripts", {})
        payload["alwayson_scripts"]["ControlNet"] = {
            "args": controlnet_units
        }
        
        return payload
    
    async def build_regional_payload(self, request: RegionalPromptRequest, session: UserSession) -> Dict:
        """Build regional prompting payload"""
        config = request.regional_config
        
        # Build regional prompt string
        prompt_parts = [config.common_prompt, "ADDCOMM", config.region1_prompt]
        
        if config.layout == "vertical":
            prompt_parts.extend(["ADDCOL", config.region2_prompt])
        elif config.layout == "horizontal":
            prompt_parts.extend(["ADDROW", config.region2_prompt])
        elif config.layout == "three_columns":
            r3 = config.region3_prompt or config.region1_prompt
            prompt_parts.extend(["ADDCOL", config.region2_prompt, "ADDCOL", r3])
        elif config.layout == "four_columns":
            r3 = config.region3_prompt or config.region1_prompt
            r4 = config.region4_prompt or config.region2_prompt
            prompt_parts.extend(["ADDCOL", config.region2_prompt, "ADDCOL", r3, "ADDCOL", r4])
        elif config.layout == "quadrants":
            r3 = config.region3_prompt or config.region1_prompt
            r4 = config.region4_prompt or config.region2_prompt
            prompt_parts.extend(["ADDCOL", config.region2_prompt, "ADDROW", r3, "ADDCOL", r4])
        
        # Apply LoRAs from session
        lora_prompt = self._build_lora_prompt(session.active_loras)
        full_prompt = f"{' '.join(prompt_parts)} {lora_prompt}".strip()
        
        # Build base payload
        base_payload = await self.build_txt2img_payload(request, session)
        base_payload["prompt"] = full_prompt
        
        # Add Regional Prompter configuration
        from ..constants import REGIONAL_PROMPTER_CONFIGS
        regional_config = REGIONAL_PROMPTER_CONFIGS.get(config.layout)
        
        if regional_config:
            base_payload["alwayson_scripts"] = base_payload.get("alwayson_scripts", {})
            base_payload["alwayson_scripts"]["Regional Prompter"] = regional_config
        
        return base_payload
    
    async def queue_generation(self, payload: Dict, user_id: str, generation_type: str) -> str:
        """Queue a generation job"""
        job_id = str(uuid.uuid4())
        
        self.job_queue[job_id] = {
            "id": job_id,
            "user_id": user_id,
            "type": generation_type,
            "payload": payload,
            "status": "queued",
            "created_at": datetime.utcnow(),
            "progress": 0.0
        }
        
        # Start processing (in real implementation, this would be a proper job queue)
        asyncio.create_task(self._process_job(job_id))
        
        return job_id
    
    async def _process_job(self, job_id: str):
        """Process a queued job"""
        if job_id not in self.job_queue:
            return
        
        job = self.job_queue[job_id]
        
        try:
            job["status"] = "processing"
            
            # Determine endpoint
            endpoint = "txt2img"
            if job["type"] in ["img2img", "controlnet"]:
                endpoint = "img2img"
            elif job["type"] == "regional":
                endpoint = "txt2img"
            
            # Make API call to A1111
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/{endpoint}",
                    json=job["payload"]
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # Store result
                        self.job_results[job_id] = {
                            "job_id": job_id,
                            "status": "completed",
                            "images": result.get("images", []),
                            "info": json.loads(result.get("info", "{}")),
                            "parameters": result.get("parameters", {}),
                            "completed_at": datetime.utcnow()
                        }
                        
                        job["status"] = "completed"
                    else:
                        error_text = await response.text()
                        self.job_results[job_id] = {
                            "job_id": job_id,
                            "status": "failed",
                            "error": f"HTTP {response.status}: {error_text}",
                            "completed_at": datetime.utcnow()
                        }
                        job["status"] = "failed"
        
        except Exception as e:
            self.job_results[job_id] = {
                "job_id": job_id,
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.utcnow()
            }
            job["status"] = "failed"
    
    async def get_job_status(self, job_id: str) -> JobStatus:
        """Get job status"""
        if job_id not in self.job_queue:
            raise Exception("Job not found")
        
        job = self.job_queue[job_id]
        return JobStatus(
            job_id=job_id,
            status=job["status"],
            progress=job.get("progress", 0.0),
            message=job.get("message", ""),
            created_at=job["created_at"],
            completed_at=job.get("completed_at")
        )
    
    async def get_job_result(self, job_id: str) -> JobResult:
        """Get job result"""
        if job_id not in self.job_results:
            raise Exception("Job result not available")
        
        result = self.job_results[job_id]
        return JobResult(**result)
    
    def _build_lora_prompt(self, active_loras: Dict[str, float]) -> str:
        """Build LoRA prompt string from active LoRAs"""
        if not active_loras:
            return ""
        
        lora_strings = []
        for filename, weight in active_loras.items():
            # Remove file extension for prompt
            lora_name = filename.replace('.safetensors', '').replace('.ckpt', '').replace('.pt', '')
            lora_strings.append(f"<lora:{lora_name}:{weight}>")
        
        return " ".join(lora_strings)
    
    async def _process_uploaded_image(self, image_file) -> str:
        """Process uploaded image file to base64"""
        contents = await image_file.read()
        
        # Open with PIL and convert to RGB if needed
        image = Image.open(io.BytesIO(contents))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert to base64
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        
        return base64.b64encode(buffer.read()).decode('utf-8')