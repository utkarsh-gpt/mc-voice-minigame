"""Block word detection from transcripts."""
import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime

from .config import Config

logger = logging.getLogger(__name__)


class BlockDetector:
    """Detects Minecraft block names from transcribed text."""
    
    def __init__(self, block_words_file: Path):
        """Initialize the block detector with block word mappings."""
        self.block_words_file = block_words_file
        self.block_words: Dict[str, str] = {}
        self.load_block_words()
    
    def load_block_words(self):
        """Load block word mappings from JSON file."""
        try:
            if self.block_words_file.exists():
                with open(self.block_words_file, 'r', encoding='utf-8') as f:
                    self.block_words = json.load(f)
                logger.info(f"Loaded {len(self.block_words)} block word mappings")
            else:
                logger.warning(f"Block words file not found: {self.block_words_file}")
                # Create default file
                self._create_default_block_words()
        except Exception as e:
            logger.error(f"Error loading block words: {e}", exc_info=True)
            self._create_default_block_words()
    
    def _create_default_block_words(self):
        """Create default block words file."""
        default_words = {
            "stone": "minecraft:stone",
            "cobblestone": "minecraft:cobblestone",
            "dirt": "minecraft:dirt",
            "diamond block": "minecraft:diamond_block",
            "gold block": "minecraft:gold_block"
        }
        self.block_words = default_words
        try:
            self.block_words_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.block_words_file, 'w', encoding='utf-8') as f:
                json.dump(default_words, f, indent=2)
            logger.info("Created default block words file")
        except Exception as e:
            logger.error(f"Error creating default block words file: {e}", exc_info=True)
    
    def normalize_text(self, text: str) -> str:
        """
        Normalize text for matching.
        
        Args:
            text: Raw transcript text
            
        Returns:
            Normalized text (lowercase, punctuation removed)
        """
        # Convert to lowercase
        text = text.lower()
        
        # Remove punctuation but keep spaces
        text = re.sub(r'[^\w\s]', '', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        return text
    
    def detect_block(self, text: str, user_id: Optional[int] = None) -> Optional[Dict]:
        """
        Detect a block name in the transcribed text.
        
        Uses whole-word matching so a key matches only when it appears as a complete
        word. This avoids false positives from background noise (e.g. "sandstone"
        won't trigger "sand" or "stone" when the transcriber mishears noise).
        Longer phrases are tried first so "diamond block" wins over "diamond".
        
        Args:
            text: Transcribed text
            user_id: Discord user ID who spoke
            
        Returns:
            Dictionary with block_id, user_id, radius if detected, None otherwise
        """
        normalized = self.normalize_text(text)
        
        # Longer phrases first so e.g. "diamond block" wins over "diamond"
        sorted_words = sorted(self.block_words.items(), key=lambda x: len(x[0]), reverse=True)
        
        for word, block_id in sorted_words:
            normalized_word = self.normalize_text(word)
            
            # Whole-word match only: key must appear as a full word (not inside another word)
            # so "sandstone" from noise doesn't trigger "sand" or "stone"
            pattern = r'\b' + re.escape(normalized_word) + r'\b'
            if re.search(pattern, normalized):
                # Try to extract radius if specified
                radius = self._extract_radius(normalized)
                
                logger.info(f"Detected block: {block_id} (triggered by user {user_id}, radius: {radius})")
                
                return {
                    'block_id': block_id,
                    'user_id': user_id,
                    'radius': radius or Config.DEFAULT_RADIUS,
                    'original_text': text,
                    'matched_word': word,
                    'timestamp': datetime.now()
                }
        
        return None
    
    def _extract_radius(self, text: str) -> Optional[int]:
        """
        Extract radius from text if specified.
        
        Examples:
            "replace with stone in 5 blocks" -> 5
            "stone radius 3" -> 3
            "diamond block 10" -> 10
        """
        # Look for patterns like "in X blocks", "radius X", "X blocks"
        patterns = [
            r'in\s+(\d+)\s+blocks?',
            r'radius\s+(\d+)',
            r'(\d+)\s+blocks?',
            r'(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    radius = int(match.group(1))
                    # Clamp to max radius
                    radius = min(radius, Config.MAX_RADIUS)
                    return radius
                except ValueError:
                    continue
        
        return None
    
    def add_block_word(self, word: str, block_id: str) -> bool:
        """
        Add a new block word mapping.
        
        Args:
            word: Word or phrase to detect
            block_id: Minecraft block ID (e.g., "minecraft:stone")
            
        Returns:
            True if successful, False otherwise
        """
        try:
            normalized_word = self.normalize_text(word)
            self.block_words[normalized_word] = block_id
            
            # Save to file
            self.block_words_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.block_words_file, 'w', encoding='utf-8') as f:
                json.dump(self.block_words, f, indent=2)
            
            logger.info(f"Added block word mapping: {word} -> {block_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding block word: {e}", exc_info=True)
            return False
    
    def remove_block_word(self, word: str) -> bool:
        """
        Remove a block word mapping.
        
        Args:
            word: Word or phrase to remove
            
        Returns:
            True if successful, False otherwise
        """
        try:
            normalized_word = self.normalize_text(word)
            
            if normalized_word not in self.block_words:
                logger.warning(f"Block word not found: {word}")
                return False
            
            del self.block_words[normalized_word]
            
            # Save to file
            with open(self.block_words_file, 'w', encoding='utf-8') as f:
                json.dump(self.block_words, f, indent=2)
            
            logger.info(f"Removed block word mapping: {word}")
            return True
        except Exception as e:
            logger.error(f"Error removing block word: {e}", exc_info=True)
            return False
    
    def get_block_words(self) -> Dict[str, str]:
        """Get all block word mappings."""
        return self.block_words.copy()


# Global block detector instance
_block_detector: Optional[BlockDetector] = None


def get_block_detector() -> BlockDetector:
    """Get or create the global block detector instance."""
    global _block_detector
    if _block_detector is None:
        _block_detector = BlockDetector(Config.BLOCK_WORDS_FILE)
    return _block_detector
