import io
import base64
import aiohttp
import asyncio
import discord
import calendar
from datetime import datetime, timedelta
from PIL import Image
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal, Tuple, Coroutine

from constants import (ADETAILER_ARGS, REGIONAL_PROMPTER_ARGS, REGIONAL_PROMPTER_CONFIGS, API_ENDPOINT, LOADING_EMOJI, IMAGE_COOLDOWN,
                       CHECKPOINT_CHOICES, UPSCALER_CHOICES, RESOLUTION_CHOICES, PDXL_CHECKPOINT_CHOICES,
                       VIP_USER_IDS, MAX_IMG2IMG_SIZE, PDXL_ORIENTATION_CHOICES, ILLUSTRIOUS_CHECKPOINTS,)
from lora_manager import LoRAManager

def scale_to_size(width: int, height: int, size: int) -> Tuple[int, int]:
    scale = (size / (width * height)) ** 0.5
    return int(width * scale), int(height * scale)


class ImageActionView(discord.ui.View):
    """Action buttons for generated images to trigger Wan2GP bot functions"""
    
    def __init__(self, prompt: str, checkpoint: str, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.prompt = prompt
        self.checkpoint = checkpoint
    
    @discord.ui.button(label="🎬 Animate", style=discord.ButtonStyle.primary, custom_id="wan2gp_animate")
    async def animate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Store context in custom_id for Wan2GP bot to handle
        await interaction.response.send_message(
            f"🎬 **Animation Request Sent**\n"
            f"The Wan2GP bot will handle this animation request.\n"
            f"Original prompt: *{self.prompt[:100]}...*", 
            ephemeral=True
        )
    
    @discord.ui.button(label="🗣️ Make Speak", style=discord.ButtonStyle.secondary, custom_id="wan2gp_speak")
    async def speak_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Store context for Wan2GP bot to handle  
        await interaction.response.send_message(
            f"🗣️ **Speech Request Sent**\n"
            f"The Wan2GP bot will handle this talking head request.\n"
            f"You'll be prompted to enter text to speak.", 
            ephemeral=True
        )
    
    async def on_timeout(self):
        # Disable buttons after timeout
        for item in self.children:
            item.disabled = True


class DreamCog(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.queue: list[Tuple[Coroutine, discord.Interaction]] = []
        self.queue_task: Optional[asyncio.Task] = None
        self.generating: dict[int, bool] = {}
        self.last_img: dict[int, datetime] = {}
        self.lora_manager = LoRAManager()

    def queue_add(self, interaction: discord.Interaction, payload: dict):
        print(f"{interaction.user.name} added to the queue")
        self.generating[interaction.user.id] = True
        self.queue.append((self.fulfill_request(interaction, payload), interaction))
        if not self.queue_task or self.queue_task.done():
            self.queue_task = asyncio.create_task(self.consume_queue())

    async def consume_queue(self):
        new = True
        while self.queue:
            task, interaction = self.queue.pop(0)
            alive = True
            if not new:
                try:
                    await interaction.edit_original_response(content=f"{LOADING_EMOJI} `Generating image...`")
                except discord.errors.NotFound:
                    self.generating[interaction.user.id] = False
                    alive = False
                except Exception as e:
                    print(f"Editing message in queue: {e}")
            if self.queue:
                asyncio.create_task(self.edit_queue_messages())
            if alive:
                await task
            new = False

    async def edit_queue_messages(self):
        tasks = [ctx.edit_original_response(content=f"{LOADING_EMOJI} `Position in queue: {i + 1}`")
                 for i, (task, ctx) in enumerate(self.queue)]
        await asyncio.gather(*tasks, return_exceptions=True)

    def get_loading_message(self):
        if self.queue_task and not self.queue_task.done():
            return f"{LOADING_EMOJI} `Position in queue: {len(self.queue) + 1}`"
        else:
            return f"{LOADING_EMOJI} `Generating image...`"

    async def fulfill_request(self, interaction: discord.Interaction, payload: dict):
        if "init_images" in payload:
            url = API_ENDPOINT + "img2img"
        else:
            url = API_ENDPOINT + "txt2img"

        # Contact the webui api
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        response.raise_for_status()
                    data = await response.json()
        except aiohttp.ClientConnectorError:
            await interaction.edit_original_response(content="Timed out! The AI server is offline.")
        except Exception as e:
            print(f"Generating image: {e}")
            content = "There was a problem getting your image. Please contact the bot owner for details."
            await interaction.edit_original_response(content=content)
        finally:
            # Reset cooldown whether it was a success or fail
            self.generating[interaction.user.id] = False
            self.last_img[interaction.user.id] = datetime.utcnow()

        # Save images to memory and send them
        files = []
        for i in range(len(data["images"])):
            image_data = base64.b64decode(data["images"][i])
            image_stream = io.BytesIO(image_data)
            file = discord.File(image_stream, filename=f"image{i+1}.png")
            files.append(file)
        
        # Add action buttons for cross-bot integration
        # Extract prompt from payload if available
        prompt_from_payload = payload.get("prompt", "Generated image")
        checkpoint_from_payload = payload.get("override_settings", {}).get("sd_model_checkpoint", "Unknown")
        
        view = ImageActionView(prompt=prompt_from_payload, checkpoint=checkpoint_from_payload)
        await interaction.edit_original_response(content="", attachments=files, view=view)

    # Commands go after this point

    @app_commands.command(name="dream", description="Generates an AI image using Stable Diffusion.")
    @app_commands.choices(checkpoint=CHECKPOINT_CHOICES, orientation=RESOLUTION_CHOICES, upscaler=UPSCALER_CHOICES)
    @app_commands.describe(prompt="What you want to generate.",
                           checkpoint="The AI model you want to use.",
                           orientation="The resolution of your image.",
                           upscaler="The AI upscaler you want to use.")
    async def dream_command(
            self,
            interaction: discord.Interaction,
            prompt: str,
            checkpoint: str,
            orientation: str,
            upscaler: str
    ):
        # Check cooldown
        if interaction.user.id not in VIP_USER_IDS:
            if self.generating.get(interaction.user.id, False):
                content = "Your current image must finish generating before you can request another one."
                return await interaction.response.send_message(content=content, ephemeral=True)
            if interaction.user.id in self.last_img and (datetime.utcnow() - self.last_img[interaction.user.id]).seconds < IMAGE_COOLDOWN:
                eta = self.last_img[interaction.user.id] + timedelta(seconds=IMAGE_COOLDOWN)
                content = f"You may use this command again <t:{calendar.timegm(eta.utctimetuple())}:R>."
                return await interaction.response.send_message(content=content, ephemeral=True)

        # Get user's active LoRAs
        lora_config = self.lora_manager.build_lora_payload(interaction.user.id)
        lora_prompt = lora_config.get("lora_prompt_additions", "")
        
        payload = {
            "prompt": f"masterpiece, best quality, {prompt} {lora_prompt}",
            "negative_prompt": "(worst quality, low quality:2), interlocked fingers, badly drawn hands and fingers, anatomically incorrect hands,",
            "sampler_name": "DPM++ 2M Karras",
            "steps": 26,
            "cfg_scale": 6.5,
            "denoising_strength": 0.40,
            "width": int(orientation.split("x")[0]),
            "height": int(orientation.split("x")[1]),
            "override_settings": {
                "sd_model_checkpoint": checkpoint,
                "sd_vae": "vae-ft-mse-840000-ema-pruned.safetensors",
            },
            "override_settings_restore_afterwards": "True",
            "enable_hr": "True",
            "hr_scale": 2,
            "hr_upscaler": upscaler,
            "hr_second_pass_steps": "14",
            "alwayson_scripts": {
                "ADetailer": ADETAILER_ARGS
            }
        }

        # Add task to the queue
        content = self.get_loading_message()
        self.queue_add(interaction, payload)
        await interaction.response.send_message(content=content)

    @app_commands.command(name="redream", description="Converts an existing image using Stable Diffusion AI.")
    @app_commands.choices(checkpoint=CHECKPOINT_CHOICES, orientation=RESOLUTION_CHOICES)
    @app_commands.describe(image="The image you want the AI to use as a base.",
                           prompt="What you want to generate.",
                           checkpoint="The AI model you want to use.",
                           orientation="The resolution of your image.",
                           denoising="How much you want the image to change. Try 0.6")
    async def img2img_command(
            self,
            interaction: discord.Interaction,
            image: discord.Attachment,
            prompt: str,
            checkpoint: str,
            orientation: str,
            denoising: app_commands.Range[float, 0.0, 1.0],
    ):
        # Check cooldown
        if interaction.user.id not in VIP_USER_IDS:
            if self.generating.get(interaction.user.id, False):
                content = "Your current image must finish generating before you can request another one."
                return await interaction.response.send_message(content=content, ephemeral=True)
            if interaction.user.id in self.last_img and (
                    datetime.utcnow() - self.last_img[interaction.user.id]).seconds < IMAGE_COOLDOWN:
                eta = self.last_img[interaction.user.id] + timedelta(seconds=IMAGE_COOLDOWN)
                content = f"You may use this command again <t:{calendar.timegm(eta.utctimetuple())}:R>."
                return await interaction.response.send_message(content=content, ephemeral=True)

        if not image.content_type.startswith("image/"):
            return await interaction.response.send_message("The file you uploaded is not a valid image.", ephemeral=True)

        # Make Discord wait while we download the image
        await interaction.response.defer()

        # Save and resize the image if necessary
        fp = io.BytesIO()
        await image.save(fp)
        if image.width * image.height > MAX_IMG2IMG_SIZE:
            width, height = scale_to_size(image.width, image.height, MAX_IMG2IMG_SIZE)
            resized_image = Image.open(fp).resize((width, height), Image.Resampling.LANCZOS)
            fp = io.BytesIO()
            resized_image.save(fp, "PNG")
            fp.seek(0)
        encoded_image = base64.b64encode(fp.read()).decode("utf8")

        payload = {
            "prompt": f"masterpiece, best quality, {prompt}",
            "negative_prompt": "(worst quality, low quality:2), interlocked fingers, badly drawn hands and fingers, anatomically incorrect hands,",
            "sampler_name": "DPM++ 2M Karras",
            "steps": 30,
            "cfg_scale": 6.5,
            "width": int(orientation.split("x")[0]),
            "height": int(orientation.split("x")[1]),
            "override_settings": {
                "sd_model_checkpoint": checkpoint
            },
            "override_settings_restore_afterwards": "True",
            "init_images": [encoded_image],
            "denoising_strength": denoising,
            "alwayson_scripts": {
                "ADetailer": ADETAILER_ARGS
            }
        }

        # Add task to the queue
        content = self.get_loading_message()
        self.queue_add(interaction, payload)
        await interaction.edit_original_response(content=content)

    @app_commands.command(name="catnap", description="Generates an image with preset options")
    @app_commands.choices(orientation=PDXL_ORIENTATION_CHOICES)
    async def catnap_command(
            self,
            interaction: discord.Interaction,
            preset: Literal["Atomix", "Retro", "Illustrious", "Laura", "Unholy", "NAI Love - Real"],
            #checkpoint: str,
            orientation: str,
            prompt: str,
            neg_prompt: str,
            batch_size: Literal[1, 2, 4]
    ):
        # Check cooldown
        if interaction.user.id not in VIP_USER_IDS:
            if self.generating.get(interaction.user.id, False):
                content = "Your current image must finish generating before you can request another one."
                return await interaction.response.send_message(content, ephemeral=True)
            if interaction.user.id in self.last_img and (datetime.utcnow() - self.last_img[interaction.user.id]).seconds < IMAGE_COOLDOWN:
                eta = self.last_img[interaction.user.id] + timedelta(seconds=IMAGE_COOLDOWN)
                content = f"You may use this command again <t:{calendar.timegm(eta.utctimetuple())}:R>."
                return await interaction.response.send_message(content, ephemeral=True)
   
        if preset == "Retro":
            payload = {
                "prompt": f"masterpiece,best quality, highly detailed, score_9, score_8_up, score_7_up, score_6_up, {prompt}",
                "negative_prompt": "3d, monochrome, simple background,watermark, patreon username, artist name, signature, text",
                "sampler_name": "Euler A",
                "steps": 26,
                "cfg_scale": 6,
                "denoising_strength": 0.44,
                "width": int(orientation.split("x")[0]),
                "height": int(orientation.split("x")[1]),
                "override_settings": {
                    "sd_model_checkpoint": "pottasticpdxl_"
                },
                "override_settings_restore_afterwards": "True",
                "enable_hr": "True",
                "hr_scale": 2,
                "hr_upscaler": "4x-AnimeSharp",
                "hr_second_pass_steps": "14",
                "alwayson_scripts": {
                    "ADetailer": ADETAILER_ARGS
                }
            }
        elif preset == "realistic":
            payload = {
                "prompt": f"score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up, realistic {prompt}",
                "negative_prompt": "(score_1, score_2, score_3), sketch, worst quality, low quality, deformed, censored, bad anatomy, patreon, logo, ",
                "sampler_name": "DPM++ 2M SDE SGMUniform",
                "steps": 20,
                "cfg_scale": 4,
                "denoising_strength": 0.15,
                "width": int(orientation.split("x")[0]),
                "height": int(orientation.split("x")[1]),
                "override_settings": {
                    "sd_model_checkpoint": "2dnPony_v10Play"
                },
                "override_settings_restore_afterwards": "True",
                "enable_hr": "True",
                "hr_scale": 2,
                "hr_upscaler": "4xRealWebPhoto_v4_dat2",
                "hr_second_pass_steps": "10",
                "alwayson_scripts": {
                    "ADetailer": ADETAILER_ARGS
                }
            }
        elif preset == "Unholy":
            payload = {
                "prompt": f"masterpiece, best quality, {prompt}",
                "negative_prompt": f"worst quality, low quality, lowres, jpeg artifacts, bad anatomy, bad hands, watermark, {neg_prompt}",
                "sampler_name": "Euler a",
                "batch_size": batch_size,
                "steps": 28,
                "denoising_strength": 0.15,
                "width": int(orientation.split("x")[0]),
                "height": int(orientation.split("x")[1]),
                "override_settings": {
                    "sd_model_checkpoint": "holyMixIllustriousxl_v1"
                },
                "override_settings_restore_afterwards": "True",
                "enable_hr": "False",
                "hr_scale": 2,
                "hr_upscaler": "4x-UltraSharp",
                "hr_second_pass_steps": "10",
                "alwayson_scripts": {
                    "ADetailer": ADETAILER_ARGS
                }
            }       
        elif preset == "Laura":
            payload = {
                "prompt": f"masterpiece, best quality, {prompt}",
                "negative_prompt": f"worst quality, low quality, bad anatomy, watermark, username, patreon, {neg_prompt}",
                "sampler_name": "Euler a",
                "batch_size": batch_size,
                "steps": 24,
                "denoising_strength": 0.15,
                "width": int(orientation.split("x")[0]),
                "height": int(orientation.split("x")[1]),
                "override_settings": {
                    "sd_model_checkpoint": "pasanctuarySDXL_v40"
                },
                "override_settings_restore_afterwards": "True",
                "enable_hr": "False",
                "hr_scale": 2,
                "hr_upscaler": "4x-UltraSharp",
                "hr_second_pass_steps": "10",
                "alwayson_scripts": {
                    "ADetailer": ADETAILER_ARGS
                }
            }
        elif preset == "Illustrious":
            payload = {
                "prompt": f"masterpiece, best quality, {prompt}",
                "negative_prompt": f"worst quality, low quality, bad anatomy, watermark, username, patreon, {neg_prompt}",
                "sampler_name": "Euler a",
                "batch_size": batch_size,
                "steps": 24,
                "denoising_strength": 0.15,
                "width": int(orientation.split("x")[0]),
                "height": int(orientation.split("x")[1]),
                "override_settings": {
                    "sd_model_checkpoint": "pasanctuarySDXL_v40"
                },
                "override_settings_restore_afterwards": "True",
                "enable_hr": "True",
                "hr_scale": 2,
                "hr_upscaler": "4x-UltraSharp",
                "hr_second_pass_steps": "10",
                "alwayson_scripts": {
                    "ADetailer": ADETAILER_ARGS
                }
            }
        elif preset == "Atomix":
            payload = {
                "prompt": f"score_8, score_6_up, 8k RAW photo, film grain, realistic, {prompt}",
                "negative_prompt": "(worst quality, low quality:1.4), (deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, wrong anatomy, extra limb, missing limb, floating limbs, (mutated hands and fingers:1.4), patreon, logo,",
                "sampler_name": "DPM++ 2M SDE SGMUniform",
                "steps": 14,
                "cfg_scale": 2,
                "denoising_strength": 0.44,
                "width": int(orientation.split("x")[0]),
                "height": int(orientation.split("x")[1]),
                "override_settings": {
                    "sd_model_checkpoint": "atomixPonyRealismXL_v10"
                },
                "override_settings_restore_afterwards": "True",
                "enable_hr": "False",
                "hr_scale": 2,
                "hr_upscaler": "4x-UltraSharp",
                "hr_second_pass_steps": "18",
                "alwayson_scripts": {
                    "ADetailer": ADETAILER_ARGS
                }
            }
        elif preset == "PDXL":
            payload = {
                "prompt": f"{prompt}",
                "negative_prompt": "greyscale,simple background,3d,blurry,monochrome,text,watermark,nose,patreon",
                "sampler_name": "Euler a",
                "batch_size": batch_size,
                "steps": 26,
                "cfg_scale": 5.5,
                "denoising_strength": 0.44,
                "width": int(orientation.split("x")[0]),
                "height": int(orientation.split("x")[1]),
                "override_settings": {
                "sd_model_checkpoint": checkpoint,
                "sd_vae": "sdxl_vae.safetensors",
                },
                "override_settings_restore_afterwards": True,  # Removed quotes from True
                "enable_hr": False,  # Removed quotes from True
                "hr_scale": 1.5,
                "hr_upscaler": "4x-AnimeSharp",
                "hr_second_pass_steps": 12,  # Removed quotes from number
                "alwayson_scripts": {
                    "ADetailer": ADETAILER_ARGS
                }
            }
        elif preset == "NAI Love - Real":
            payload = {
                "prompt": f"masterpiece, best quality, {prompt}",
                "negative_prompt": f"worst quality, low quality, {neg_prompt}",
                "sampler_name": "Euler a",
                "batch_size": batch_size,
                "steps": 35,
                "cfg_scale": 7,
                "denoising_strength": 0.15,
                "width": int(orientation.split("x")[0]),
                "height": int(orientation.split("x")[1]),
                "override_settings": {
                    "sd_model_checkpoint": "nailoveNoobaiRealSDXL_v03Contrastes",
                    "sd_vae": "sdxl_vae.safetensors",
                    "CLIP_stop_at_last_layers": 2
                },
                "override_settings_restore_afterwards": "True",
                "enable_hr": "False",
                "hr_scale": 2,
                "hr_upscaler": "4x-UltraSharp",
                "hr_second_pass_steps": "10",
                "alwayson_scripts": {
                    "ADetailer": ADETAILER_ARGS
                }
            }
        # Add task to the queue
        content = self.get_loading_message()
        self.queue_add(interaction, payload)
        await interaction.response.send_message(content=content)


    @app_commands.command(name="regional", description="Advanced regional prompting with multiple layouts")
    @app_commands.choices(orientation=PDXL_ORIENTATION_CHOICES)
    async def regional_command(
        self,
        interaction: discord.Interaction,
        layout: Literal["vertical", "horizontal", "three_columns", "four_columns", "quadrants"],
        orientation: str,
        common_prompt: str,
        region1_prompt: str,
        region2_prompt: str,
        region3_prompt: Optional[str] = None,
        region4_prompt: Optional[str] = None,
        batch_size: Literal["1"] = "1"
    ):
        # Check cooldown
        if interaction.user.id not in VIP_USER_IDS:
            if self.generating.get(interaction.user.id, False):
                content = "Your current image must finish generating before you can request another one."
                return await interaction.response.send_message(content, ephemeral=True)
            if interaction.user.id in self.last_img and (datetime.utcnow() - self.last_img[interaction.user.id]).seconds < IMAGE_COOLDOWN:
                eta = self.last_img[interaction.user.id] + timedelta(seconds=IMAGE_COOLDOWN)
                content = f"You may use this command again <t:{calendar.timegm(eta.utctimetuple())}:R>."
                return await interaction.response.send_message(content, ephemeral=True)

        # Get regional configuration
        config = REGIONAL_PROMPTER_CONFIGS[layout]
        separators = config["separators"]
        
        # Build prompt based on layout
        if layout == "vertical":
            # Left/Right: common ADDCOMM left ADDCOL right  
            prompt_parts = [common_prompt, "ADDCOMM", region1_prompt, "ADDCOL", region2_prompt]
        elif layout == "horizontal":
            # Top/Bottom: common ADDCOMM top ADDROW bottom
            prompt_parts = [common_prompt, "ADDCOMM", region1_prompt, "ADDROW", region2_prompt]
        elif layout == "three_columns":
            # Left/Center/Right: common ADDCOMM left ADDCOL center ADDCOL right
            r3 = region3_prompt or region1_prompt  # Default to region1 if not provided
            prompt_parts = [common_prompt, "ADDCOMM", region1_prompt, "ADDCOL", region2_prompt, "ADDCOL", r3]
        elif layout == "four_columns":
            # Four columns: common ADDCOMM col1 ADDCOL col2 ADDCOL col3 ADDCOL col4
            r3 = region3_prompt or region1_prompt  # Default to region1 if not provided
            r4 = region4_prompt or region2_prompt  # Default to region2 if not provided
            prompt_parts = [common_prompt, "ADDCOMM", region1_prompt, "ADDCOL", region2_prompt, "ADDCOL", r3, "ADDCOL", r4]
        elif layout == "quadrants":
            # Four corners (2x2): common ADDCOMM tl ADDCOL tr ADDROW bl ADDCOL br
            r3 = region3_prompt or region1_prompt  # Default to region1 if not provided
            r4 = region4_prompt or region2_prompt  # Default to region2 if not provided
            prompt_parts = [common_prompt, "ADDCOMM", region1_prompt, "ADDCOL", region2_prompt, "ADDROW", r3, "ADDCOL", r4]

        # Get user's active LoRAs
        lora_config = self.lora_manager.build_lora_payload(interaction.user.id)
        lora_prompt = lora_config.get("lora_prompt_additions", "")
        
        # Build final prompt
        full_prompt = f"masterpiece, best quality, {' '.join(prompt_parts)} {lora_prompt}"

        payload = {
            "prompt": full_prompt,
            "negative_prompt": "worst quality, low quality, bad anatomy, watermark, username, patreon,",
            "sampler_name": "Euler a",
            "batch_size": batch_size,
            "steps": 26,
            "cfg_scale": 6,
            "denoising_strength": 0.20,
            "width": int(orientation.split("x")[0]),
            "height": int(orientation.split("x")[1]),
            "override_settings": {
                "sd_model_checkpoint": "holyMixIllustriousxl_v1",
                "sd_vae": "sdxl_vae.safetensors",
            },
            "override_settings_restore_afterwards": True,
            "enable_hr": True,
            "hr_scale": 1.5,
            "hr_upscaler": "4x-UltraSharp",
            "hr_second_pass_steps": 10,
            "alwayson_scripts": {
                "Regional Prompter": config,
                "ADetailer": ADETAILER_ARGS
            }
        }

        # Add task to the queue
        content = self.get_loading_message()
        self.queue_add(interaction, payload)
        await interaction.response.send_message(content=content)

    @app_commands.command(name="lora", description="Add LoRA to your current session")
    @app_commands.describe(
        name="Search for LoRA by name or tags",
        weight="LoRA strength (0.1-2.0, recommended: 0.6-1.0)"
    )
    async def lora_add_command(
        self,
        interaction: discord.Interaction,
        name: str,
        weight: app_commands.Range[float, 0.1, 2.0] = 0.8
    ):
        # Find the LoRA by name/filename
        lora = self.lora_manager.get_lora_by_filename(name)
        if not lora:
            # Try searching for it
            matches = self.lora_manager.search_loras(name, limit=1)
            if not matches:
                return await interaction.response.send_message(
                    f"LoRA '{name}' not found. Use autocomplete to find available LoRAs.", 
                    ephemeral=True
                )
            lora = matches[0]
            name = lora["filename"]

        # Add to user session
        self.lora_manager.add_lora_to_session(interaction.user.id, name, weight)
        
        embed = discord.Embed(
            title="✅ LoRA Added",
            description=f"**{lora['name']}** (weight: {weight})",
            color=0x00ff00
        )
        if lora.get("trigger_words"):
            embed.add_field(
                name="Trigger Words", 
                value=", ".join(lora["trigger_words"]), 
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @lora_add_command.autocomplete('name')
    async def lora_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if not current:
            return []
        return self.lora_manager.get_lora_autocomplete_choices(current)

    @app_commands.command(name="lora-current", description="View your currently active LoRAs")
    async def loras_list_command(self, interaction: discord.Interaction):
        active_loras = self.lora_manager.get_user_session_loras(interaction.user.id)
        
        if not active_loras:
            return await interaction.response.send_message("No active LoRAs in your session.", ephemeral=True)
        
        embed = discord.Embed(title="🎨 Active LoRAs", color=0x0099ff)
        
        for filename, weight in active_loras.items():
            lora = self.lora_manager.get_lora_by_filename(filename)
            name = lora["name"] if lora else filename
            embed.add_field(name=name, value=f"Weight: {weight}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="lora-clear", description="Clear all LoRAs from your session")
    async def lora_clear_command(self, interaction: discord.Interaction):
        self.lora_manager.clear_user_loras(interaction.user.id)
        await interaction.response.send_message("✅ All LoRAs cleared from your session.", ephemeral=True)

# Add this module to the bot
async def setup(bot):
    await bot.add_cog(DreamCog(bot))
