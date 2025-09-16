import json
import os
import aiohttp
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime
import re
from pathlib import Path

from .models import LoRAInfo

class APILoRAManager:
    def __init__(self, config_path: str = "data/loras.json", a1111_url: str = "http://127.0.0.1:7860"):
        self.config_path = config_path
        self.a1111_url = a1111_url
        self.loras_db: Dict[str, Any] = {"loras": [], "last_updated": None, "version": "1.0"}
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Load existing database
        self._load_database()
    
    def _load_database(self):
        """Load LoRA database from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.loras_db = json.load(f)
        except Exception as e:
            print(f"Error loading LoRA database: {e}")
            self.loras_db = {"loras": [], "last_updated": None, "version": "1.0"}
    
    def _save_database(self):
        """Save LoRA database to file"""
        try:
            self.loras_db["last_updated"] = datetime.utcnow().isoformat()
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.loras_db, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving LoRA database: {e}")
    
    async def scan_a1111_loras(self) -> Dict[str, Any]:
        """Scan A1111 installation for LoRAs and update database"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.a1111_url}/sdapi/v1/loras") as response:
                    if response.status == 200:
                        a1111_loras = await response.json()
                        return await self._update_database_from_a1111(a1111_loras)
                    else:
                        raise Exception(f"Failed to get LoRAs from A1111: {response.status}")
        except Exception as e:
            print(f"Error scanning A1111 LoRAs: {e}")
            # Fallback: scan file system
            return await self._scan_filesystem()
    
    async def _update_database_from_a1111(self, a1111_loras: List[Dict]) -> Dict[str, Any]:
        """Update database with LoRAs from A1111 API"""
        new_count = 0
        updated_count = 0
        
        # Create lookup for existing LoRAs
        existing_loras = {lora["filename"]: lora for lora in self.loras_db["loras"]}
        
        for lora_data in a1111_loras:
            filename = lora_data.get("name", "")
            if not filename:
                continue
            
            # Extract metadata from A1111 response
            lora_info = self._extract_lora_metadata(lora_data)
            
            if filename in existing_loras:
                # Update existing LoRA
                existing_loras[filename].update(lora_info)
                updated_count += 1
            else:
                # Add new LoRA
                self.loras_db["loras"].append(lora_info)
                new_count += 1
        
        self._save_database()
        
        return {
            "count": len(self.loras_db["loras"]),
            "new": new_count,
            "updated": updated_count,
            "total_scanned": len(a1111_loras)
        }
    
    async def _scan_filesystem(self) -> Dict[str, Any]:
        """Fallback: scan filesystem for LoRA files"""
        # Common LoRA directories
        possible_paths = [
            "models/Lora",
            "models/lora", 
            "../stable-diffusion-webui/models/Lora",
            "../automatic1111/models/Lora"
        ]
        
        lora_files = []
        for path_str in possible_paths:
            path = Path(path_str)
            if path.exists():
                for ext in ['*.safetensors', '*.ckpt', '*.pt']:
                    lora_files.extend(path.glob(ext))
                break
        
        new_count = 0
        for lora_file in lora_files:
            if not any(lora["filename"] == lora_file.name for lora in self.loras_db["loras"]):
                lora_info = self._extract_metadata_from_filename(lora_file.name)
                self.loras_db["loras"].append(lora_info)
                new_count += 1
        
        self._save_database()
        
        return {
            "count": len(self.loras_db["loras"]),
            "new": new_count,
            "updated": 0,
            "total_scanned": len(lora_files)
        }
    
    def _extract_lora_metadata(self, lora_data: Dict) -> Dict[str, Any]:
        """Extract LoRA metadata from A1111 response"""
        filename = lora_data.get("name", "")
        
        # Basic metadata
        metadata = {
            "filename": filename,
            "name": self._clean_filename_for_display(filename),
            "tags": self._extract_tags_from_filename(filename),
            "trigger_words": [],
            "strength_range": [0.6, 1.0],
            "description": None,
            "thumbnail": None,
            "civitai_id": None
        }
        
        # Try to extract additional metadata if available
        if "metadata" in lora_data:
            meta = lora_data["metadata"]
            if "ss_tag_frequency" in meta:
                # Extract common tags from training data
                try:
                    tag_freq = json.loads(meta["ss_tag_frequency"])
                    common_tags = []
                    for dataset, tags in tag_freq.items():
                        if isinstance(tags, dict):
                            # Get most frequent tags
                            sorted_tags = sorted(tags.items(), key=lambda x: x[1], reverse=True)
                            common_tags.extend([tag for tag, freq in sorted_tags[:10] if freq > 5])
                    
                    metadata["tags"].extend(list(set(common_tags))[:20])  # Limit to 20 tags
                except:
                    pass
            
            # Extract trigger words if available
            if "ss_sd_model_name" in meta:
                metadata["description"] = f"Trained on {meta['ss_sd_model_name']}"
        
        return metadata
    
    def _extract_metadata_from_filename(self, filename: str) -> Dict[str, Any]:
        """Extract metadata from filename when A1111 API isn't available"""
        return {
            "filename": filename,
            "name": self._clean_filename_for_display(filename),
            "tags": self._extract_tags_from_filename(filename),
            "trigger_words": [],
            "strength_range": [0.6, 1.0],
            "description": None,
            "thumbnail": None,
            "civitai_id": None
        }
    
    def _clean_filename_for_display(self, filename: str) -> str:
        """Clean filename for display purposes"""
        # Remove extension
        name = re.sub(r'\.(safetensors|ckpt|pt)$', '', filename, flags=re.IGNORECASE)
        
        # Replace underscores and hyphens with spaces
        name = re.sub(r'[_-]+', ' ', name)
        
        # Remove version numbers and hashes
        name = re.sub(r'[vV]\d+[\d.]*', '', name)
        name = re.sub(r'[a-fA-F0-9]{8,}', '', name)
        
        # Clean up extra spaces and capitalize
        name = ' '.join(name.split())
        return name.title()
    
    def _extract_tags_from_filename(self, filename: str) -> List[str]:
        """Extract potential tags from filename"""
        tags = []
        filename_lower = filename.lower()
        
        # Character/series detection
        character_patterns = [
            r'(\w+)(?:_v\d+|_\d+|$)',  # Character names
            r'(\w+)(?:_lora|_model)',   # Model names
        ]
        
        for pattern in character_patterns:
            matches = re.findall(pattern, filename_lower)
            tags.extend(matches)
        
        # Style tags
        style_keywords = [
            'realistic', 'anime', 'manga', 'cartoon', '3d', '2d',
            'portrait', 'landscape', 'concept', 'style', 'art',
            'character', 'outfit', 'pose', 'background'
        ]
        
        for keyword in style_keywords:
            if keyword in filename_lower:
                tags.append(keyword)
        
        # Remove duplicates and return
        return list(set(tags))
    
    def search_loras(self, query: str, limit: int = 50) -> List[LoRAInfo]:
        """Search LoRAs by name and tags"""
        if not query:
            return self.get_all_loras(limit)
        
        query_lower = query.lower()
        matches = []
        
        for lora_data in self.loras_db["loras"]:
            score = 0
            
            # Name matching (highest priority)
            if query_lower in lora_data["name"].lower():
                score += 10
            
            # Filename matching
            if query_lower in lora_data["filename"].lower():
                score += 8
            
            # Tag matching
            for tag in lora_data.get("tags", []):
                if query_lower in tag.lower():
                    score += 5
            
            # Trigger word matching
            for trigger in lora_data.get("trigger_words", []):
                if query_lower in trigger.lower():
                    score += 3
            
            # Description matching
            if lora_data.get("description") and query_lower in lora_data["description"].lower():
                score += 2
            
            if score > 0:
                matches.append((score, LoRAInfo(**lora_data)))
        
        # Sort by relevance and return
        matches.sort(key=lambda x: x[0], reverse=True)
        return [lora for _, lora in matches[:limit]]
    
    def get_all_loras(self, limit: int = 50) -> List[LoRAInfo]:
        """Get all LoRAs with limit"""
        loras = []
        for lora_data in self.loras_db["loras"][:limit]:
            try:
                loras.append(LoRAInfo(**lora_data))
            except Exception as e:
                print(f"Error creating LoRAInfo for {lora_data.get('filename', 'unknown')}: {e}")
                continue
        return loras
    
    def get_lora_by_filename(self, filename: str) -> Optional[LoRAInfo]:
        """Get specific LoRA by filename"""
        for lora_data in self.loras_db["loras"]:
            if lora_data["filename"] == filename:
                try:
                    return LoRAInfo(**lora_data)
                except Exception as e:
                    print(f"Error creating LoRAInfo for {filename}: {e}")
                    return None
        return None
    
    def add_lora(self, lora_info: Dict[str, Any]) -> bool:
        """Add new LoRA to database"""
        try:
            # Check if already exists
            if any(lora["filename"] == lora_info["filename"] for lora in self.loras_db["loras"]):
                return False
            
            self.loras_db["loras"].append(lora_info)
            self._save_database()
            return True
        except Exception as e:
            print(f"Error adding LoRA: {e}")
            return False
    
    def update_lora(self, filename: str, updates: Dict[str, Any]) -> bool:
        """Update existing LoRA"""
        try:
            for i, lora in enumerate(self.loras_db["loras"]):
                if lora["filename"] == filename:
                    self.loras_db["loras"][i].update(updates)
                    self._save_database()
                    return True
            return False
        except Exception as e:
            print(f"Error updating LoRA: {e}")
            return False
    
    def delete_lora(self, filename: str) -> bool:
        """Delete LoRA from database"""
        try:
            original_count = len(self.loras_db["loras"])
            self.loras_db["loras"] = [
                lora for lora in self.loras_db["loras"] 
                if lora["filename"] != filename
            ]
            
            if len(self.loras_db["loras"]) < original_count:
                self._save_database()
                return True
            return False
        except Exception as e:
            print(f"Error deleting LoRA: {e}")
            return False
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        tags_count = {}
        for lora in self.loras_db["loras"]:
            for tag in lora.get("tags", []):
                tags_count[tag] = tags_count.get(tag, 0) + 1
        
        return {
            "total_loras": len(self.loras_db["loras"]),
            "last_updated": self.loras_db.get("last_updated"),
            "version": self.loras_db.get("version"),
            "most_common_tags": sorted(tags_count.items(), key=lambda x: x[1], reverse=True)[:10]
        }
    
    async def update_civitai_metadata(self, limit: int = 10) -> int:
        """Update LoRA metadata from CivitAI (if available)"""
        # This would require CivitAI API integration
        # For now, just return 0
        return 0