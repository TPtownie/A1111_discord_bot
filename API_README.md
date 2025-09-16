# Discord Bot A1111 API

A comprehensive HTTP API that unlocks ALL Automatic1111 features for both Discord bots and mobile applications.

## 🚀 Quick Start

### Prerequisites
```bash
pip install -r requirements.txt
```

### Start the API Server
```bash
python start_api.py --host 0.0.0.0 --port 8000 --a1111-url http://127.0.0.1:7860
```

### API Documentation
- **Interactive Docs**: http://localhost:8000/docs
- **OpenAPI Spec**: http://localhost:8000/openapi.json
- **Health Check**: http://localhost:8000/health

## 📱 Multi-Platform Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Discord Bot   │    │   iOS/Mobile    │    │   Web Interface │
│   (Simplified)  │    │   (Full Power)  │    │   (Optional)    │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────┴───────────────┐
                    │      FastAPI Backend       │
                    │   (All A1111 Features)     │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────┴───────────────┐
                    │   Automatic1111 WebUI      │
                    │    (Stable Diffusion)      │
                    └─────────────────────────────┘
```

## 🎯 Key Features

### ✅ Complete A1111 Integration
- **All Models**: Dynamic checkpoint, VAE, sampler access
- **LoRA Management**: Smart search, autocomplete, session persistence
- **ControlNet**: Full multi-ControlNet support with preprocessing
- **Regional Prompting**: Advanced layout control
- **Inpainting/Outpainting**: Complete masking support
- **Batch Generation**: Multiple variations and settings

### ✅ Advanced Session Management  
- **Per-User Sessions**: Persistent LoRA/ControlNet configurations
- **Preset System**: Save and load complete workflows
- **Real-time Status**: Job queue and progress tracking
- **Cross-Platform**: Same session across Discord and mobile

### ✅ Smart Search & Discovery
- **LoRA Database**: Metadata extraction and tagging
- **Auto-Scanning**: Discovers LoRAs from A1111 installation
- **Fuzzy Search**: Name, tag, and description matching
- **Model Information**: Complete checkpoint and extension data

## 📚 API Endpoints

### Health & System
```http
GET /health                    # Check API and A1111 status
GET /models                   # Get all available models/checkpoints
```

### LoRA Management
```http
GET /loras?search={query}      # Search LoRAs with autocomplete
POST /loras/scan              # Scan A1111 for new LoRAs
```

### Session Management
```http
GET /sessions/{user_id}        # Get user's current session
POST /sessions/{user_id}/loras # Add LoRA to session
DELETE /sessions/{user_id}/loras/{filename} # Remove LoRA
DELETE /sessions/{user_id}/loras # Clear all LoRAs
```

### Generation Endpoints
```http
POST /generate/txt2img        # Text to image generation
POST /generate/img2img        # Image to image generation  
POST /generate/controlnet     # ControlNet generation
POST /generate/regional       # Regional prompting generation
```

### Job Management
```http
GET /jobs/{job_id}            # Get job status and progress
GET /jobs/{job_id}/result     # Get completed job results
```

### Preset Management
```http
GET /presets/{user_id}        # Get user's saved presets
POST /presets/{user_id}       # Save new preset
DELETE /presets/{user_id}/{preset_id} # Delete preset
```

### ControlNet Features
```http
GET /controlnet/models        # Get available ControlNet models
POST /controlnet/preprocess   # Preprocess images for ControlNet
```

## 🔧 Usage Examples

### Basic Text Generation
```python
import requests

# Add LoRA to session
requests.post("http://localhost:8000/sessions/user123/loras", json={
    "filename": "character_lora.safetensors",
    "weight": 0.8
})

# Generate image
response = requests.post("http://localhost:8000/generate/txt2img", json={
    "user_id": "user123",
    "prompt": "beautiful anime girl, detailed face",
    "negative_prompt": "low quality, blurry",
    "checkpoint": "animefull_final.safetensors",
    "width": 512,
    "height": 768,
    "steps": 20,
    "cfg_scale": 7.0,
    "sampler_name": "DPM++ 2M Karras"
})

job_id = response.json()["job_id"]
```

### ControlNet Generation
```python
import requests

# Upload reference image and generate with ControlNet
with open("pose_reference.jpg", "rb") as f:
    files = {"image": f}
    data = {
        "user_id": "user123",
        "prompt": "detailed portrait, studio lighting",
        "controlnet_units": [{
            "enabled": True,
            "model": "control_openpose-fp16",
            "weight": 1.0,
            "preprocessor": "openpose_full"
        }]
    }
    
    response = requests.post(
        "http://localhost:8000/generate/controlnet",
        files=files,
        data=data
    )
```

### Regional Prompting
```python
import requests

response = requests.post("http://localhost:8000/generate/regional", json={
    "user_id": "user123", 
    "prompt": "masterpiece, high quality",
    "regional_config": {
        "layout": "three_columns",
        "common_prompt": "fantasy tavern scene",
        "region1_prompt": "knight in armor drinking",
        "region2_prompt": "fireplace with warm lighting", 
        "region3_prompt": "bard playing lute"
    },
    "width": 768,
    "height": 512,
    "steps": 25
})
```

### Check Job Status
```python
import requests
import time

job_id = "your-job-id"

while True:
    status = requests.get(f"http://localhost:8000/jobs/{job_id}").json()
    print(f"Status: {status['status']}, Progress: {status.get('progress', 0):.1%}")
    
    if status["status"] == "completed":
        result = requests.get(f"http://localhost:8000/jobs/{job_id}/result").json()
        images = result["images"]  # Base64 encoded images
        break
    elif status["status"] == "failed":
        print(f"Generation failed: {status.get('message')}")
        break
    
    time.sleep(2)
```

## 🔒 Discord vs iOS/Mobile Capabilities

### Discord Bot (Simplified Interface)
- ✅ Basic generation commands
- ✅ LoRA search and management  
- ✅ Regional prompting presets
- ✅ Session persistence
- ❌ Limited to 25 autocomplete options
- ❌ Single file upload only
- ❌ No advanced parameter control
- ❌ No real-time progress feedback

### iOS/Mobile App (Full Power)
- ✅ **Complete model browser** with thumbnails
- ✅ **Advanced parameter controls** (sliders, pickers)
- ✅ **Multi-image uploads** for ControlNet
- ✅ **Batch generation** with variations
- ✅ **Real-time progress** tracking
- ✅ **Visual workflow builder**
- ✅ **Image management** and galleries
- ✅ **Preset sharing** between users

## 🏗️ Data Structure

### Session Structure
```json
{
  "user_id": "user123",
  "active_loras": {
    "character_lora.safetensors": 0.8,
    "style_lora.safetensors": 0.6
  },
  "controlnet_configs": [
    {
      "model": "control_openpose-fp16",
      "weight": 1.0,
      "preprocessor": "openpose_full"
    }
  ],
  "custom_settings": {
    "preferred_sampler": "DPM++ 2M Karras",
    "default_steps": 20
  },
  "last_updated": "2025-01-04T12:00:00"
}
```

### Generation Request Example
```json
{
  "user_id": "user123",
  "prompt": "masterpiece, detailed anime portrait",
  "negative_prompt": "low quality, blurry",
  "checkpoint": "animefull_final.safetensors",
  "vae": "vae-ft-mse-840000-ema-pruned.safetensors",
  "sampler_name": "DPM++ 2M Karras",
  "steps": 20,
  "cfg_scale": 7.0,
  "width": 512,
  "height": 768,
  "batch_count": 1,
  "batch_size": 1,
  "seed": -1,
  "enable_hr": true,
  "hr_scale": 2.0,
  "hr_upscaler": "4x-UltraSharp"
}
```

## 🚧 Development Setup

### Running in Development Mode
```bash
# Start with auto-reload for development
python start_api.py --reload --host 127.0.0.1 --port 8000

# Custom A1111 URL
python start_api.py --a1111-url http://192.168.1.100:7860
```

### Testing the API
```bash
# Health check
curl http://localhost:8000/health

# Get available models
curl http://localhost:8000/models

# Search LoRAs
curl "http://localhost:8000/loras?search=anime&limit=10"
```

### Data Directories
```
data/
├── sessions.json     # User sessions (persistent)
├── presets.json      # User presets
└── loras.json        # LoRA database
```

## 📱 iOS App Integration Examples

### Swift API Client Example
```swift
import Foundation

class A1111APIClient {
    let baseURL = "http://your-server:8000"
    
    func generateImage(request: GenerationRequest) async throws -> String {
        let url = URL(string: "\(baseURL)/generate/txt2img")!
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let data = try JSONEncoder().encode(request)
        urlRequest.httpBody = data
        
        let (responseData, _) = try await URLSession.shared.data(for: urlRequest)
        let response = try JSONDecoder().decode(GenerationResponse.self, from: responseData)
        
        return response.job_id
    }
    
    func checkJobStatus(jobId: String) async throws -> JobStatus {
        let url = URL(string: "\(baseURL)/jobs/\(jobId)")!
        let (data, _) = try await URLSession.shared.data(from: url)
        return try JSONDecoder().decode(JobStatus.self, from: data)
    }
}
```

## 🛠️ Troubleshooting

### Common Issues

**API won't start**
- Check if port 8000 is available
- Verify A1111 WebUI is running on specified URL
- Check Python dependencies: `pip install -r requirements.txt`

**LoRA search returns empty results**  
- Run `/loras/scan` endpoint to populate database
- Check A1111 LoRA directory permissions
- Verify LoRA files are in correct format (.safetensors, .ckpt, .pt)

**ControlNet models not found**
- Ensure ControlNet extension is installed in A1111
- Check ControlNet models are downloaded
- Verify A1111 API is accessible

**Generation jobs fail**
- Check A1111 WebUI logs for errors
- Verify checkpoint/model names are correct
- Check available VRAM for large generations

### Performance Tips

- Use `batch_size=1` with multiple `batch_count` for better memory usage
- Enable `pixel_perfect` for ControlNet for better results
- Use appropriate `processor_res` values (512 for most ControlNet models)
- Consider using FP16 models to save VRAM

## 🔮 Future Enhancements

- **Real-time WebSocket** progress updates
- **CivitAI Integration** for LoRA metadata  
- **Model Auto-downloading** from HuggingFace
- **Advanced Batch Operations** with parameter sweeping
- **Image Enhancement** pipeline integration
- **Custom Extension Support** for other A1111 plugins

---

This API transforms your Discord bot from a simple command interface into a powerful multi-platform AI art generation system! 🎨✨