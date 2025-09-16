from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

# LoRA Models
class LoRAInfo(BaseModel):
    filename: str
    name: str
    tags: List[str] = []
    trigger_words: List[str] = []
    strength_range: List[float] = [0.6, 1.0]
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    civitai_id: Optional[int] = None

class LoRAListResponse(BaseModel):
    loras: List[LoRAInfo]
    total: int

class AddLoRARequest(BaseModel):
    filename: str
    weight: float = Field(ge=0.1, le=2.0)

# Model Information
class ModelsResponse(BaseModel):
    checkpoints: List[str]
    vaes: List[str]
    samplers: List[str]
    upscalers: List[str]

# Session Management
class UserSession(BaseModel):
    user_id: str
    active_loras: Dict[str, float] = {}
    controlnet_configs: List[Dict] = []
    custom_settings: Dict[str, Any] = {}
    last_updated: Optional[datetime] = None

# Generation Requests
class BaseGenerationRequest(BaseModel):
    user_id: str
    prompt: str
    negative_prompt: str = ""
    checkpoint: Optional[str] = None
    vae: Optional[str] = None
    sampler_name: str = "DPM++ 2M Karras"
    steps: int = Field(default=20, ge=1, le=150)
    cfg_scale: float = Field(default=7.0, ge=1.0, le=30.0)
    width: int = Field(default=512, ge=64, le=2048)
    height: int = Field(default=512, ge=64, le=2048)
    batch_count: int = Field(default=1, ge=1, le=10)
    batch_size: int = Field(default=1, ge=1, le=4)
    seed: int = Field(default=-1, ge=-1)
    enable_hr: bool = False
    hr_scale: float = Field(default=2.0, ge=1.0, le=4.0)
    hr_upscaler: Optional[str] = None
    hr_second_pass_steps: int = Field(default=0, ge=0, le=150)
    denoising_strength: float = Field(default=0.7, ge=0.0, le=1.0)

class Txt2ImgRequest(BaseGenerationRequest):
    pass

class Img2ImgRequest(BaseGenerationRequest):
    resize_mode: int = 0
    inpaint_full_res: bool = True
    inpaint_full_res_padding: int = 0
    inpainting_mask_invert: int = 0

# ControlNet Models
class ControlNetUnit(BaseModel):
    enabled: bool = True
    model: str
    weight: float = Field(default=1.0, ge=0.0, le=2.0)
    guidance_start: float = Field(default=0.0, ge=0.0, le=1.0)
    guidance_end: float = Field(default=1.0, ge=0.0, le=1.0)
    processor_res: int = Field(default=512, ge=64, le=2048)
    threshold_a: float = Field(default=100, ge=0, le=255)
    threshold_b: float = Field(default=200, ge=0, le=255)
    control_mode: int = Field(default=0, ge=0, le=2)
    pixel_perfect: bool = False
    preprocessor: Optional[str] = None

class ControlNetRequest(BaseGenerationRequest):
    controlnet_units: List[ControlNetUnit]

# Regional Prompting
class RegionalConfig(BaseModel):
    layout: str = Field(..., regex="^(vertical|horizontal|three_columns|four_columns|quadrants)$")
    common_prompt: str
    region1_prompt: str
    region2_prompt: str
    region3_prompt: Optional[str] = None
    region4_prompt: Optional[str] = None

class RegionalPromptRequest(BaseGenerationRequest):
    regional_config: RegionalConfig

# Job Management
class GenerationResponse(BaseModel):
    job_id: str
    status: str
    message: str
    estimated_time: Optional[int] = None

class JobStatus(BaseModel):
    job_id: str
    status: str  # "queued", "processing", "completed", "failed"
    progress: Optional[float] = None
    eta_relative: Optional[float] = None
    message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

class JobResult(BaseModel):
    job_id: str
    status: str
    images: List[str] = []  # Base64 encoded images
    info: Dict[str, Any] = {}
    parameters: Dict[str, Any] = {}
    error: Optional[str] = None

# Preset Management
class SavePresetRequest(BaseModel):
    name: str
    description: Optional[str] = None
    config: Dict[str, Any]

class PresetInfo(BaseModel):
    preset_id: str
    name: str
    description: Optional[str] = None
    config: Dict[str, Any]
    created_at: datetime
    last_used: Optional[datetime] = None

# Advanced Features
class InpaintRequest(BaseGenerationRequest):
    mask_blur: int = Field(default=4, ge=0, le=64)
    inpainting_fill: int = Field(default=1, ge=0, le=3)
    inpaint_full_res: bool = True
    inpaint_full_res_padding: int = Field(default=0, ge=0, le=256)
    inpainting_mask_invert: int = Field(default=0, ge=0, le=1)

class OutpaintRequest(BaseGenerationRequest):
    outpaint_pixels_left: int = Field(default=0, ge=0, le=512)
    outpaint_pixels_right: int = Field(default=0, ge=0, le=512)
    outpaint_pixels_top: int = Field(default=0, ge=0, le=512)
    outpaint_pixels_bottom: int = Field(default=0, ge=0, le=512)

# Batch Operations
class BatchGenerationRequest(BaseModel):
    user_id: str
    base_request: BaseGenerationRequest
    variations: List[Dict[str, Any]] = []  # Parameter variations for each batch
    batch_name: Optional[str] = None

# Model Management
class ModelInfo(BaseModel):
    name: str
    title: Optional[str] = None
    model_name: str
    hash: Optional[str] = None
    sha256: Optional[str] = None
    filename: str
    config: Optional[str] = None

# Advanced Settings
class AdvancedSettings(BaseModel):
    clip_skip: int = Field(default=1, ge=1, le=12)
    ensd: int = Field(default=31337)
    eta_noise_seed_delta: int = Field(default=0)
    s_churn: float = Field(default=0.0, ge=0.0)
    s_tmax: float = Field(default=0.0, ge=0.0)
    s_tmin: float = Field(default=0.0, ge=0.0)
    s_noise: float = Field(default=1.0, ge=0.0)
    eta: float = Field(default=0.0, ge=0.0, le=1.0)

# Prompt Analysis
class PromptAnalysisRequest(BaseModel):
    prompt: str

class PromptAnalysisResponse(BaseModel):
    tokens: List[str]
    token_count: int
    attention_weights: Dict[str, float]
    suggested_improvements: List[str]
    detected_styles: List[str]
    detected_characters: List[str]

# Queue Management
class QueueStatus(BaseModel):
    position: int
    total_jobs: int
    estimated_wait_time: Optional[int] = None
    current_job_progress: Optional[float] = None

# Error Models
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime