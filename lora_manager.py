import json
import os
from typing import List, Dict, Optional
from discord import app_commands
import discord

class LoRAManager:
    def __init__(self, config_path: str = "configs/loras.json", session_path: str = "configs/current_session.json"):
        self.config_path = config_path
        self.session_path = session_path
        self.loras_db = self.load_loras_db()
        
    def load_loras_db(self) -> Dict:
        """Load LoRA database from JSON file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"loras": [], "last_updated": None, "version": "1.0"}
    
    def save_loras_db(self):
        """Save LoRA database to JSON file"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.loras_db, f, indent=2, ensure_ascii=False)
    
    def load_session(self) -> Dict:
        """Load current session configuration"""
        try:
            with open(self.session_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "active_loras": {},
                "controlnet_configs": [],
                "custom_adetailer": None,
                "style_overrides": {},
                "last_updated": None
            }
    
    def save_session(self, session_data: Dict):
        """Save current session configuration"""
        os.makedirs(os.path.dirname(self.session_path), exist_ok=True)
        with open(self.session_path, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
    
    def search_loras(self, query: str, limit: int = 25) -> List[Dict]:
        """Search LoRAs by name and tags"""
        query = query.lower()
        matches = []
        
        for lora in self.loras_db.get("loras", []):
            score = 0
            
            # Check name match
            if query in lora["name"].lower():
                score += 10
                
            # Check tags match
            for tag in lora.get("tags", []):
                if query in tag.lower():
                    score += 5
                    
            # Check trigger words match
            for trigger in lora.get("trigger_words", []):
                if query in trigger.lower():
                    score += 3
                    
            # Check filename match
            if query in lora["filename"].lower():
                score += 2
                
            if score > 0:
                matches.append((score, lora))
        
        # Sort by score (highest first) and return top results
        matches.sort(key=lambda x: x[0], reverse=True)
        return [match[1] for match in matches[:limit]]
    
    def get_lora_autocomplete_choices(self, query: str) -> List[app_commands.Choice]:
        """Get autocomplete choices for LoRA search"""
        matches = self.search_loras(query)
        choices = []
        
        for lora in matches:
            # Create choice with name as label and filename as value
            choice_name = lora["name"]
            if len(choice_name) > 100:  # Discord limit
                choice_name = choice_name[:97] + "..."
                
            choices.append(app_commands.Choice(
                name=choice_name,
                value=lora["filename"]
            ))
            
        return choices[:25]  # Discord limit
    
    def add_lora_to_session(self, user_id: int, filename: str, weight: float) -> bool:
        """Add LoRA to user's current session"""
        session = self.load_session()
        
        # Initialize user session if doesn't exist
        if str(user_id) not in session:
            session[str(user_id)] = {
                "active_loras": {},
                "controlnet_configs": [],
                "custom_adetailer": None,
                "style_overrides": {}
            }
        
        # Add LoRA to session
        session[str(user_id)]["active_loras"][filename] = weight
        
        self.save_session(session)
        return True
    
    def get_user_session_loras(self, user_id: int) -> Dict[str, float]:
        """Get user's active LoRAs"""
        session = self.load_session()
        user_session = session.get(str(user_id), {})
        return user_session.get("active_loras", {})
    
    def clear_user_loras(self, user_id: int):
        """Clear all LoRAs from user's session"""
        session = self.load_session()
        if str(user_id) in session:
            session[str(user_id)]["active_loras"] = {}
            self.save_session(session)
    
    def get_lora_by_filename(self, filename: str) -> Optional[Dict]:
        """Get LoRA details by filename"""
        for lora in self.loras_db.get("loras", []):
            if lora["filename"] == filename:
                return lora
        return None
    
    def build_lora_payload(self, user_id: int) -> Dict:
        """Build LoRA configuration for A1111 API payload"""
        active_loras = self.get_user_session_loras(user_id)
        
        if not active_loras:
            return {}
        
        # Format LoRAs for prompt inclusion
        lora_strings = []
        for filename, weight in active_loras.items():
            # Remove file extension for prompt
            lora_name = filename.replace('.safetensors', '').replace('.ckpt', '').replace('.pt', '')
            lora_strings.append(f"<lora:{lora_name}:{weight}>")
        
        return {
            "lora_prompt_additions": " ".join(lora_strings),
            "active_loras_count": len(active_loras)
        }