# Stable Diffusion Discord Bot

A feature-rich Discord bot for generating AI images using Automatic1111's Stable Diffusion WebUI. This bot provides an intuitive Discord interface for text-to-image and image-to-image generation with support for LoRAs, ControlNet, and various model checkpoints.

## Features

- **Text-to-Image Generation** - Generate images from text prompts
- **Image-to-Image** - Transform existing images with AI
- **Multiple Model Support**:
  - SD 1.5 checkpoints
  - SDXL/Pony Diffusion XL models
  - Illustrious XL models
  - Flux models
- **LoRA Management** - Search, add, and manage LoRA models with custom weights
- **Queue System** - Handles multiple generation requests efficiently
- **User Configurations** - Save and load personal generation settings
- **Cross-bot Integration** - Buttons to trigger animation/speech in companion bots
- **VIP System** - Bypass cooldowns for specific users

## Prerequisites

- Python 3.8 or higher
- [Automatic1111's Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
- Discord Bot Token
- Models installed in your A1111 installation

## Installation

1. **Clone the repository**:
```bash
git clone https://github.com/TPtownie/A1111_discord_bot
```

2. **Install Python dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure Automatic1111 WebUI**:
   
   You MUST enable the API in Automatic1111 by adding `--api` to your commandline arguments:
   
   - Edit `webui-user.bat` (Windows) or `webui-user.sh` (Linux/Mac)
   - Add `--api` to the `COMMANDLINE_ARGS` line:
   ```bash
   set COMMANDLINE_ARGS=--api
   ```
   - Optional: Add `--api-auth username:password` for authentication
   - Start the WebUI - it should be accessible at `http://127.0.0.1:7860`

4. **Set up Discord Bot**:

   a. **Create a Discord Application**:
      - Go to [Discord Developer Portal](https://discord.com/developers/applications)
      - Click "New Application" and give it a name
      - Go to the "Bot" section in the sidebar
      - Click "Add Bot"
      - Under "Token", click "Copy" to get your bot token

   b. **Configure Bot Permissions**:
      - In the "Bot" section, enable these Privileged Gateway Intents:
        - Message Content Intent
        - Server Members Intent
        - Presence Intent
      - In the "OAuth2" → "URL Generator" section:
        - Select "bot" and "applications.commands" scopes
        - Select these permissions:
          - Send Messages
          - Embed Links
          - Attach Files
          - Read Message History
          - Add Reactions
          - Use Slash Commands
      - Copy the generated URL and use it to invite the bot to your server

5. **Configure the bot**:
   - Edit `secrets.py` and replace `YOUR_DISCORD_BOT_TOKEN_HERE` with your bot token:
   ```python
   DISCORD_TOKEN = "your-actual-token-here"
   ```

6. **Update model checkpoints** (optional):
   - Edit `constants.py` to add your actual model names
   - Replace the placeholder checkpoint names with your installed models

## Running the Bot

1. **Start Automatic1111 WebUI** (with `--api` flag):
```bash
# Windows
webui-user.bat

# Linux/Mac
./webui.sh --api
```

2. **Start the API server** (optional, for advanced features):
```bash
python start_api.py
```

3. **Start the Discord bot**:
```bash
python bot.py
```

You should see "Ready" in the console when the bot is connected.

## Usage

### Basic Commands

- `/dream` - Generate an image from a text prompt
- `/img2img` - Transform an existing image
- `/lora_search` - Search for available LoRA models
- `/lora_add` - Add a LoRA to your generation settings
- `/lora_list` - View your active LoRAs
- `/lora_clear` - Remove all LoRAs from your settings

### Generation Parameters

When using `/dream` or `/img2img`, you can customize:
- **Prompt** - Your image description
- **Negative Prompt** - What to avoid in the image
- **Model** - Choose between SD1.5, SDXL, Illustrious, or Flux models
- **Resolution** - Various preset sizes
- **Steps** - Number of denoising steps (1-150)
- **CFG Scale** - Prompt adherence strength (1-30)
- **Seed** - Specific seed for reproducibility (-1 for random)
- **Upscaler** - Optional image upscaling

### LoRA Management

1. Search for LoRAs: `/lora_search query:character`
2. Add to your settings: `/lora_add filename:mylora.safetensors weight:0.7`
3. View active LoRAs: `/lora_list`
4. Clear all: `/lora_clear`

LoRAs are automatically included in your generations once added.

## Configuration Files

- `secrets.py` - Discord bot token (never commit this!)
- `constants.py` - Model lists, resolutions, API endpoints
- `configs/loras.json` - LoRA database
- `configs/current_session.json` - User session data

## Project Structure

```
├── bot.py                 # Main bot entry point
├── dream.py               # Core bot logic and commands
├── constants.py           # Configuration constants
├── lora_manager.py        # LoRA management system
├── api/                   # FastAPI server components
│   ├── main.py           # API server
│   ├── a1111_interface.py # A1111 communication
│   ├── models.py         # Data models
│   └── session_manager.py # Session handling
└── configs/              # Configuration storage
```

## Troubleshooting

1. **"Connection refused" error**:
   - Ensure A1111 is running with `--api` flag
   - Check that A1111 is accessible at `http://127.0.0.1:7860`
   - Verify no firewall is blocking the connection

2. **Bot doesn't respond to commands**:
   - Check bot has proper permissions in Discord
   - Ensure slash commands are synced (restart bot)
   - Verify bot token is correct

3. **"Model not found" errors**:
   - Update checkpoint names in `constants.py`
   - Ensure models are properly installed in A1111
   - Check model names match exactly (case-sensitive)

4. **API-related issues**:
   - If using API auth, update credentials in code
   - Check A1111 console for error messages
   - Ensure all required extensions are installed

## Security Notes

- **NEVER** commit `secrets.py` with your real token
- Use `.gitignore` to exclude sensitive files
- Consider using environment variables for production
- Enable API authentication if exposing A1111 publicly

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## License

This project is provided as-is for educational purposes.

## Acknowledgments

- [Automatic1111](https://github.com/AUTOMATIC1111/stable-diffusion-webui) for Stable Diffusion WebUI
- Discord.py community for the excellent library

- All model creators and the SD community

