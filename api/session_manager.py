import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from .models import UserSession, PresetInfo

class SessionManager:
    def __init__(self, sessions_file: str = "data/sessions.json", presets_file: str = "data/presets.json"):
        self.sessions_file = sessions_file
        self.presets_file = presets_file
        self.sessions_cache: Dict[str, UserSession] = {}
        self.presets_cache: Dict[str, Dict] = {}
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Load existing data
        self._load_sessions()
        self._load_presets()
    
    def _load_sessions(self):
        """Load sessions from file"""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for user_id, session_data in data.items():
                        # Convert datetime strings back to datetime objects
                        if session_data.get("last_updated"):
                            session_data["last_updated"] = datetime.fromisoformat(session_data["last_updated"])
                        self.sessions_cache[user_id] = UserSession(**session_data)
        except Exception as e:
            print(f"Error loading sessions: {e}")
            self.sessions_cache = {}
    
    def _save_sessions(self):
        """Save sessions to file"""
        try:
            # Convert UserSession objects to dict for JSON serialization
            data = {}
            for user_id, session in self.sessions_cache.items():
                session_dict = session.dict()
                # Convert datetime to string
                if session_dict.get("last_updated"):
                    session_dict["last_updated"] = session_dict["last_updated"].isoformat()
                data[user_id] = session_dict
            
            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving sessions: {e}")
    
    def _load_presets(self):
        """Load presets from file"""
        try:
            if os.path.exists(self.presets_file):
                with open(self.presets_file, 'r', encoding='utf-8') as f:
                    self.presets_cache = json.load(f)
        except Exception as e:
            print(f"Error loading presets: {e}")
            self.presets_cache = {}
    
    def _save_presets(self):
        """Save presets to file"""
        try:
            with open(self.presets_file, 'w', encoding='utf-8') as f:
                json.dump(self.presets_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving presets: {e}")
    
    def get_user_session(self, user_id: str) -> UserSession:
        """Get or create user session"""
        if user_id not in self.sessions_cache:
            self.sessions_cache[user_id] = UserSession(
                user_id=user_id,
                active_loras={},
                controlnet_configs=[],
                custom_settings={},
                last_updated=datetime.utcnow()
            )
            self._save_sessions()
        
        return self.sessions_cache[user_id]
    
    def update_session(self, user_id: str, session: UserSession):
        """Update user session"""
        session.last_updated = datetime.utcnow()
        self.sessions_cache[user_id] = session
        self._save_sessions()
    
    def add_lora(self, user_id: str, filename: str, weight: float) -> bool:
        """Add LoRA to user session"""
        try:
            session = self.get_user_session(user_id)
            session.active_loras[filename] = weight
            self.update_session(user_id, session)
            return True
        except Exception as e:
            print(f"Error adding LoRA: {e}")
            return False
    
    def remove_lora(self, user_id: str, filename: str) -> bool:
        """Remove LoRA from user session"""
        try:
            session = self.get_user_session(user_id)
            if filename in session.active_loras:
                del session.active_loras[filename]
                self.update_session(user_id, session)
                return True
            return False
        except Exception as e:
            print(f"Error removing LoRA: {e}")
            return False
    
    def clear_loras(self, user_id: str):
        """Clear all LoRAs from user session"""
        try:
            session = self.get_user_session(user_id)
            session.active_loras = {}
            self.update_session(user_id, session)
        except Exception as e:
            print(f"Error clearing LoRAs: {e}")
    
    def add_controlnet_config(self, user_id: str, config: Dict) -> bool:
        """Add ControlNet configuration to user session"""
        try:
            session = self.get_user_session(user_id)
            session.controlnet_configs.append(config)
            self.update_session(user_id, session)
            return True
        except Exception as e:
            print(f"Error adding ControlNet config: {e}")
            return False
    
    def clear_controlnet_configs(self, user_id: str):
        """Clear all ControlNet configurations from user session"""
        try:
            session = self.get_user_session(user_id)
            session.controlnet_configs = []
            self.update_session(user_id, session)
        except Exception as e:
            print(f"Error clearing ControlNet configs: {e}")
    
    def update_custom_settings(self, user_id: str, settings: Dict[str, Any]):
        """Update custom settings for user session"""
        try:
            session = self.get_user_session(user_id)
            session.custom_settings.update(settings)
            self.update_session(user_id, session)
        except Exception as e:
            print(f"Error updating custom settings: {e}")
    
    def save_preset(self, user_id: str, name: str, config: Dict[str, Any]) -> str:
        """Save a generation preset for user"""
        try:
            preset_id = str(uuid.uuid4())
            
            if user_id not in self.presets_cache:
                self.presets_cache[user_id] = {}
            
            self.presets_cache[user_id][preset_id] = {
                "preset_id": preset_id,
                "name": name,
                "config": config,
                "created_at": datetime.utcnow().isoformat(),
                "last_used": None
            }
            
            self._save_presets()
            return preset_id
        except Exception as e:
            print(f"Error saving preset: {e}")
            raise Exception("Failed to save preset")
    
    def get_user_presets(self, user_id: str) -> List[PresetInfo]:
        """Get user's saved presets"""
        try:
            if user_id not in self.presets_cache:
                return []
            
            presets = []
            for preset_data in self.presets_cache[user_id].values():
                preset_data_copy = preset_data.copy()
                # Convert datetime strings
                if preset_data_copy.get("created_at"):
                    preset_data_copy["created_at"] = datetime.fromisoformat(preset_data_copy["created_at"])
                if preset_data_copy.get("last_used"):
                    preset_data_copy["last_used"] = datetime.fromisoformat(preset_data_copy["last_used"])
                
                presets.append(PresetInfo(**preset_data_copy))
            
            return presets
        except Exception as e:
            print(f"Error getting presets: {e}")
            return []
    
    def get_preset(self, user_id: str, preset_id: str) -> Optional[Dict]:
        """Get specific preset"""
        try:
            if user_id in self.presets_cache and preset_id in self.presets_cache[user_id]:
                preset = self.presets_cache[user_id][preset_id].copy()
                # Update last used
                preset["last_used"] = datetime.utcnow().isoformat()
                self.presets_cache[user_id][preset_id]["last_used"] = preset["last_used"]
                self._save_presets()
                return preset
            return None
        except Exception as e:
            print(f"Error getting preset: {e}")
            return None
    
    def delete_preset(self, user_id: str, preset_id: str) -> bool:
        """Delete a preset"""
        try:
            if user_id in self.presets_cache and preset_id in self.presets_cache[user_id]:
                del self.presets_cache[user_id][preset_id]
                self._save_presets()
                return True
            return False
        except Exception as e:
            print(f"Error deleting preset: {e}")
            return False
    
    def get_session_stats(self, user_id: str) -> Dict[str, Any]:
        """Get session statistics"""
        session = self.get_user_session(user_id)
        presets = self.get_user_presets(user_id)
        
        return {
            "active_loras_count": len(session.active_loras),
            "controlnet_configs_count": len(session.controlnet_configs),
            "custom_settings_count": len(session.custom_settings),
            "presets_count": len(presets),
            "last_updated": session.last_updated.isoformat() if session.last_updated else None
        }
    
    def cleanup_old_sessions(self, days_old: int = 30):
        """Clean up sessions older than specified days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            users_to_remove = []
            
            for user_id, session in self.sessions_cache.items():
                if session.last_updated and session.last_updated < cutoff_date:
                    users_to_remove.append(user_id)
            
            for user_id in users_to_remove:
                del self.sessions_cache[user_id]
            
            if users_to_remove:
                self._save_sessions()
                print(f"Cleaned up {len(users_to_remove)} old sessions")
                
        except Exception as e:
            print(f"Error cleaning up sessions: {e}")
    
    def get_timestamp(self) -> str:
        """Get current timestamp"""
        return datetime.utcnow().isoformat()
    
    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Export all user data for backup/migration"""
        session = self.get_user_session(user_id)
        presets = self.get_user_presets(user_id)
        
        return {
            "user_id": user_id,
            "session": session.dict(),
            "presets": [preset.dict() for preset in presets],
            "exported_at": self.get_timestamp()
        }
    
    def import_user_data(self, user_data: Dict[str, Any]) -> bool:
        """Import user data from backup"""
        try:
            user_id = user_data["user_id"]
            
            # Import session
            session_data = user_data["session"]
            if session_data.get("last_updated"):
                session_data["last_updated"] = datetime.fromisoformat(session_data["last_updated"])
            self.sessions_cache[user_id] = UserSession(**session_data)
            
            # Import presets
            if "presets" in user_data:
                self.presets_cache[user_id] = {}
                for preset_data in user_data["presets"]:
                    preset_id = preset_data["preset_id"]
                    self.presets_cache[user_id][preset_id] = preset_data
            
            self._save_sessions()
            self._save_presets()
            return True
            
        except Exception as e:
            print(f"Error importing user data: {e}")
            return False