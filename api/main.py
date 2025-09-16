from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
import uvicorn
from pydantic import BaseModel
import json

from .models import *
from .a1111_interface import A1111Interface
from .session_manager import SessionManager
from .lora_manager import APILoRAManager
from .controlnet_manager import ControlNetManager

app = FastAPI(
    title="Discord Bot A1111 API",
    description="Comprehensive API for Automatic1111 integration with Discord bot and mobile apps",
    version="1.0.0"
)

# CORS middleware for mobile app access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
a1111 = A1111Interface()
sessions = SessionManager()
loras = APILoRAManager()
controlnet = ControlNetManager()

# Health check
@app.get("/health")
async def health_check():
    """Check if the API and A1111 are running"""
    try:
        status = await a1111.check_status()
        return {
            "status": "healthy",
            "a1111_status": status,
            "timestamp": sessions.get_timestamp()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"A1111 not available: {str(e)}")

# Model management
@app.get("/models", response_model=ModelsResponse)
async def get_models():
    """Get all available models/checkpoints"""
    try:
        models = await a1111.get_models()
        return ModelsResponse(
            checkpoints=models.get("checkpoints", []),
            vaes=models.get("vaes", []),
            samplers=models.get("samplers", []),
            upscalers=models.get("upscalers", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# LoRA management
@app.get("/loras", response_model=LoRAListResponse)
async def get_loras(search: Optional[str] = None, limit: int = 50):
    """Get available LoRAs with optional search"""
    try:
        if search:
            lora_list = loras.search_loras(search, limit)
        else:
            lora_list = loras.get_all_loras(limit)
        
        return LoRAListResponse(loras=lora_list, total=len(lora_list))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/loras/scan")
async def scan_loras():
    """Scan A1111 installation for LoRAs and update database"""
    try:
        result = await loras.scan_a1111_loras()
        return {"message": f"Scanned and found {result['count']} LoRAs", "details": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Session management
@app.get("/sessions/{user_id}", response_model=UserSession)
async def get_session(user_id: str):
    """Get user's current session"""
    session = sessions.get_user_session(user_id)
    return session

@app.post("/sessions/{user_id}/loras")
async def add_lora_to_session(user_id: str, lora_request: AddLoRARequest):
    """Add LoRA to user session"""
    try:
        success = sessions.add_lora(user_id, lora_request.filename, lora_request.weight)
        if success:
            return {"message": "LoRA added to session", "session": sessions.get_user_session(user_id)}
        else:
            raise HTTPException(status_code=400, detail="Failed to add LoRA")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sessions/{user_id}/loras/{lora_filename}")
async def remove_lora_from_session(user_id: str, lora_filename: str):
    """Remove LoRA from user session"""
    success = sessions.remove_lora(user_id, lora_filename)
    if success:
        return {"message": "LoRA removed from session"}
    else:
        raise HTTPException(status_code=404, detail="LoRA not found in session")

@app.delete("/sessions/{user_id}/loras")
async def clear_session_loras(user_id: str):
    """Clear all LoRAs from user session"""
    sessions.clear_loras(user_id)
    return {"message": "All LoRAs cleared from session"}

# ControlNet management
@app.get("/controlnet/models")
async def get_controlnet_models():
    """Get available ControlNet models"""
    try:
        models = await controlnet.get_available_models()
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/controlnet/preprocess")
async def preprocess_controlnet_image(
    file: UploadFile = File(...),
    processor: str = "canny"
):
    """Preprocess image for ControlNet"""
    try:
        result = await controlnet.preprocess_image(file, processor)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Generation endpoints
@app.post("/generate/txt2img", response_model=GenerationResponse)
async def generate_txt2img(request: Txt2ImgRequest):
    """Generate image from text prompt"""
    try:
        # Get user session and merge with request
        session = sessions.get_user_session(request.user_id)
        payload = await a1111.build_txt2img_payload(request, session)
        
        # Queue the generation
        job_id = await a1111.queue_generation(payload, request.user_id, "txt2img")
        
        return GenerationResponse(
            job_id=job_id,
            status="queued",
            message="Generation queued successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/img2img", response_model=GenerationResponse)
async def generate_img2img(request: Img2ImgRequest, image: UploadFile = File(...)):
    """Generate image from image + text prompt"""
    try:
        session = sessions.get_user_session(request.user_id)
        payload = await a1111.build_img2img_payload(request, session, image)
        
        job_id = await a1111.queue_generation(payload, request.user_id, "img2img")
        
        return GenerationResponse(
            job_id=job_id,
            status="queued",
            message="Generation queued successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/controlnet", response_model=GenerationResponse)
async def generate_with_controlnet(
    request: ControlNetRequest,
    image: UploadFile = File(...),
    mask: Optional[UploadFile] = File(None)
):
    """Generate image with ControlNet"""
    try:
        session = sessions.get_user_session(request.user_id)
        payload = await a1111.build_controlnet_payload(request, session, image, mask)
        
        job_id = await a1111.queue_generation(payload, request.user_id, "controlnet")
        
        return GenerationResponse(
            job_id=job_id,
            status="queued",
            message="ControlNet generation queued successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/regional", response_model=GenerationResponse)
async def generate_with_regional_prompter(request: RegionalPromptRequest):
    """Generate image with regional prompting"""
    try:
        session = sessions.get_user_session(request.user_id)
        payload = await a1111.build_regional_payload(request, session)
        
        job_id = await a1111.queue_generation(payload, request.user_id, "regional")
        
        return GenerationResponse(
            job_id=job_id,
            status="queued",
            message="Regional prompting generation queued successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Job status and results
@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get generation job status"""
    try:
        status = await a1111.get_job_status(job_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=404, detail="Job not found")

@app.get("/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    """Get generation job result"""
    try:
        result = await a1111.get_job_result(job_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=404, detail="Job result not available")

# Preset management
@app.get("/presets/{user_id}")
async def get_user_presets(user_id: str):
    """Get user's saved presets"""
    presets = sessions.get_user_presets(user_id)
    return {"presets": presets}

@app.post("/presets/{user_id}")
async def save_preset(user_id: str, preset: SavePresetRequest):
    """Save a generation preset"""
    try:
        preset_id = sessions.save_preset(user_id, preset.name, preset.config)
        return {"message": "Preset saved", "preset_id": preset_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/presets/{user_id}/{preset_id}")
async def delete_preset(user_id: str, preset_id: str):
    """Delete a saved preset"""
    success = sessions.delete_preset(user_id, preset_id)
    if success:
        return {"message": "Preset deleted"}
    else:
        raise HTTPException(status_code=404, detail="Preset not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)