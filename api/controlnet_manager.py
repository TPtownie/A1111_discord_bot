import aiohttp
import asyncio
import base64
import io
import json
from typing import List, Dict, Optional, Any
from PIL import Image, ImageFilter, ImageOps
import cv2
import numpy as np

class ControlNetManager:
    def __init__(self, a1111_url: str = "http://127.0.0.1:7860"):
        self.a1111_url = a1111_url
        self.available_models: List[str] = []
        self.preprocessors = {
            "canny": self._canny_preprocessor,
            "depth": self._depth_preprocessor,
            "openpose": self._openpose_preprocessor,
            "scribble": self._scribble_preprocessor,
            "seg": self._seg_preprocessor,
            "normal": self._normal_preprocessor,
            "lineart": self._lineart_preprocessor,
            "softedge": self._softedge_preprocessor
        }
    
    async def get_available_models(self) -> List[str]:
        """Get available ControlNet models from A1111"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.a1111_url}/controlnet/model_list") as response:
                    if response.status == 200:
                        data = await response.json()
                        self.available_models = data.get("model_list", [])
                        return self.available_models
                    else:
                        # Fallback list if API not available
                        self.available_models = [
                            "control_canny-fp16",
                            "control_depth-fp16", 
                            "control_openpose-fp16",
                            "control_scribble-fp16",
                            "control_seg-fp16",
                            "control_normal-fp16",
                            "control_lineart-fp16",
                            "control_softedge-fp16"
                        ]
                        return self.available_models
        except Exception as e:
            print(f"Error getting ControlNet models: {e}")
            return self.available_models
    
    async def get_available_preprocessors(self) -> Dict[str, Dict[str, Any]]:
        """Get available ControlNet preprocessors"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.a1111_url}/controlnet/module_list") as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._format_preprocessor_info(data.get("module_list", []))
                    else:
                        return self._get_default_preprocessors()
        except Exception as e:
            print(f"Error getting ControlNet preprocessors: {e}")
            return self._get_default_preprocessors()
    
    def _get_default_preprocessors(self) -> Dict[str, Dict[str, Any]]:
        """Get default preprocessor information"""
        return {
            "canny": {
                "name": "Canny Edge Detection",
                "description": "Detects edges in the image",
                "parameters": ["threshold_a", "threshold_b"],
                "recommended_models": ["control_canny-fp16"]
            },
            "depth": {
                "name": "Depth Estimation", 
                "description": "Estimates depth information",
                "parameters": [],
                "recommended_models": ["control_depth-fp16"]
            },
            "openpose": {
                "name": "Human Pose Detection",
                "description": "Detects human poses and keypoints",
                "parameters": [],
                "recommended_models": ["control_openpose-fp16"]
            },
            "scribble": {
                "name": "Scribble/Sketch",
                "description": "Converts to scribble-like lines",
                "parameters": [],
                "recommended_models": ["control_scribble-fp16"]
            },
            "seg": {
                "name": "Semantic Segmentation",
                "description": "Segments image into different regions",
                "parameters": [],
                "recommended_models": ["control_seg-fp16"]
            },
            "normal": {
                "name": "Normal Map",
                "description": "Generates surface normals",
                "parameters": [],
                "recommended_models": ["control_normal-fp16"]
            },
            "lineart": {
                "name": "Line Art",
                "description": "Converts to clean line art",
                "parameters": [],
                "recommended_models": ["control_lineart-fp16"]
            },
            "softedge": {
                "name": "Soft Edge",
                "description": "Soft edge detection",
                "parameters": [],
                "recommended_models": ["control_softedge-fp16"]
            }
        }
    
    def _format_preprocessor_info(self, module_list: List[str]) -> Dict[str, Dict[str, Any]]:
        """Format preprocessor info from A1111 response"""
        preprocessor_info = {}
        default_info = self._get_default_preprocessors()
        
        for module in module_list:
            # Extract base preprocessor name
            base_name = module.split('_')[0] if '_' in module else module
            
            if base_name in default_info:
                preprocessor_info[module] = {
                    **default_info[base_name],
                    "module_name": module
                }
            else:
                preprocessor_info[module] = {
                    "name": module.replace('_', ' ').title(),
                    "description": f"ControlNet preprocessor: {module}",
                    "parameters": [],
                    "recommended_models": [],
                    "module_name": module
                }
        
        return preprocessor_info
    
    async def preprocess_image(self, image_file, preprocessor: str, **kwargs) -> Dict[str, Any]:
        """Preprocess image using specified preprocessor"""
        try:
            # First try A1111 API preprocessing
            processed_image = await self._api_preprocess(image_file, preprocessor, **kwargs)
            if processed_image:
                return {
                    "status": "success",
                    "processed_image": processed_image,
                    "preprocessor": preprocessor,
                    "method": "api"
                }
            
            # Fallback to local preprocessing
            processed_image = await self._local_preprocess(image_file, preprocessor, **kwargs)
            return {
                "status": "success", 
                "processed_image": processed_image,
                "preprocessor": preprocessor,
                "method": "local"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "preprocessor": preprocessor
            }
    
    async def _api_preprocess(self, image_file, preprocessor: str, **kwargs) -> Optional[str]:
        """Use A1111 API for preprocessing"""
        try:
            # Read and encode image
            contents = await image_file.read()
            image_b64 = base64.b64encode(contents).decode('utf-8')
            
            payload = {
                "controlnet_module": preprocessor,
                "controlnet_input_images": [image_b64],
                "controlnet_processor_res": kwargs.get("processor_res", 512),
                "controlnet_threshold_a": kwargs.get("threshold_a", 100),
                "controlnet_threshold_b": kwargs.get("threshold_b", 200)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.a1111_url}/controlnet/detect",
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("images", [None])[0]
                    return None
                    
        except Exception as e:
            print(f"API preprocessing failed: {e}")
            return None
    
    async def _local_preprocess(self, image_file, preprocessor: str, **kwargs) -> str:
        """Local preprocessing fallback"""
        # Reset file pointer
        await image_file.seek(0)
        contents = await image_file.read()
        
        # Open with PIL
        image = Image.open(io.BytesIO(contents))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Apply preprocessing
        if preprocessor in self.preprocessors:
            processed = await self.preprocessors[preprocessor](image, **kwargs)
        else:
            # Default: return original image
            processed = image
        
        # Convert back to base64
        buffer = io.BytesIO()
        processed.save(buffer, format='PNG')
        buffer.seek(0)
        
        return base64.b64encode(buffer.read()).decode('utf-8')
    
    async def _canny_preprocessor(self, image: Image.Image, **kwargs) -> Image.Image:
        """Canny edge detection"""
        try:
            # Convert to numpy array
            img_array = np.array(image)
            
            # Convert to grayscale
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            # Apply Canny edge detection
            threshold_a = kwargs.get("threshold_a", 100)
            threshold_b = kwargs.get("threshold_b", 200)
            edges = cv2.Canny(gray, threshold_a, threshold_b)
            
            # Convert back to PIL Image
            return Image.fromarray(edges, mode='L').convert('RGB')
        except:
            # Fallback: PIL-based edge detection
            return image.filter(ImageFilter.FIND_EDGES)
    
    async def _depth_preprocessor(self, image: Image.Image, **kwargs) -> Image.Image:
        """Depth estimation (simplified)"""
        # Simplified depth: convert to grayscale and apply some processing
        gray = image.convert('L')
        # Apply some filtering to simulate depth
        depth = gray.filter(ImageFilter.GaussianBlur(radius=1))
        return depth.convert('RGB')
    
    async def _openpose_preprocessor(self, image: Image.Image, **kwargs) -> Image.Image:
        """OpenPose preprocessing (simplified)"""
        # This would require actual pose detection - for now return edge-detected version
        return await self._canny_preprocessor(image, **kwargs)
    
    async def _scribble_preprocessor(self, image: Image.Image, **kwargs) -> Image.Image:
        """Scribble preprocessing"""
        # Convert to sketch-like image
        gray = image.convert('L')
        edges = gray.filter(ImageFilter.FIND_EDGES)
        return edges.convert('RGB')
    
    async def _seg_preprocessor(self, image: Image.Image, **kwargs) -> Image.Image:
        """Segmentation preprocessing (simplified)"""
        # Simplified segmentation - posterize the image
        posterized = ImageOps.posterize(image, bits=3)
        return posterized
    
    async def _normal_preprocessor(self, image: Image.Image, **kwargs) -> Image.Image:
        """Normal map preprocessing (simplified)"""
        # Convert to grayscale and tint blue (normal maps are typically blue-ish)
        gray = image.convert('L')
        normal = Image.merge('RGB', (gray, gray, gray))
        return normal
    
    async def _lineart_preprocessor(self, image: Image.Image, **kwargs) -> Image.Image:
        """Line art preprocessing"""
        # Convert to line art using edge detection and inversion
        gray = image.convert('L')
        edges = gray.filter(ImageFilter.FIND_EDGES)
        inverted = ImageOps.invert(edges)
        return inverted.convert('RGB')
    
    async def _softedge_preprocessor(self, image: Image.Image, **kwargs) -> Image.Image:
        """Soft edge preprocessing"""
        # Soft edge detection with blur
        gray = image.convert('L')
        blurred = gray.filter(ImageFilter.GaussianBlur(radius=0.5))
        edges = blurred.filter(ImageFilter.FIND_EDGES)
        return edges.convert('RGB')
    
    def get_recommended_settings(self, model_name: str) -> Dict[str, Any]:
        """Get recommended settings for specific ControlNet model"""
        settings_map = {
            "canny": {
                "weight": 1.0,
                "guidance_start": 0.0,
                "guidance_end": 1.0,
                "control_mode": 0,
                "recommended_preprocessors": ["canny"],
                "typical_threshold_a": 100,
                "typical_threshold_b": 200
            },
            "depth": {
                "weight": 1.0,
                "guidance_start": 0.0,
                "guidance_end": 1.0,
                "control_mode": 0,
                "recommended_preprocessors": ["depth_midas", "depth_leres"],
                "processor_res": 384
            },
            "openpose": {
                "weight": 1.0,
                "guidance_start": 0.0,
                "guidance_end": 1.0,
                "control_mode": 0,
                "recommended_preprocessors": ["openpose_full", "openpose"],
                "processor_res": 512
            },
            "scribble": {
                "weight": 1.0,
                "guidance_start": 0.0,
                "guidance_end": 1.0,
                "control_mode": 0,
                "recommended_preprocessors": ["scribble_pidinet", "scribble_hed"],
                "processor_res": 512
            }
        }
        
        # Find matching settings
        for key, settings in settings_map.items():
            if key in model_name.lower():
                return settings
        
        # Default settings
        return {
            "weight": 1.0,
            "guidance_start": 0.0,
            "guidance_end": 1.0,
            "control_mode": 0,
            "processor_res": 512
        }
    
    def validate_controlnet_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean ControlNet configuration"""
        cleaned = {
            "enabled": config.get("enabled", True),
            "model": config.get("model", ""),
            "weight": max(0.0, min(2.0, config.get("weight", 1.0))),
            "guidance_start": max(0.0, min(1.0, config.get("guidance_start", 0.0))),
            "guidance_end": max(0.0, min(1.0, config.get("guidance_end", 1.0))),
            "processor_res": max(64, min(2048, config.get("processor_res", 512))),
            "threshold_a": max(0, min(255, config.get("threshold_a", 100))),
            "threshold_b": max(0, min(255, config.get("threshold_b", 200))),
            "control_mode": max(0, min(2, config.get("control_mode", 0))),
            "pixel_perfect": config.get("pixel_perfect", False)
        }
        
        # Ensure guidance_start <= guidance_end
        if cleaned["guidance_start"] > cleaned["guidance_end"]:
            cleaned["guidance_start"], cleaned["guidance_end"] = cleaned["guidance_end"], cleaned["guidance_start"]
        
        return cleaned
    
    def get_control_mode_descriptions(self) -> Dict[int, str]:
        """Get descriptions for control modes"""
        return {
            0: "Balanced - Standard control strength",
            1: "My prompt is more important - Reduce ControlNet influence", 
            2: "ControlNet is more important - Increase ControlNet influence"
        }