"""Configuration management for the Discord Minecraft bot."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    """Bot configuration loaded from environment variables."""
    
    # Discord Configuration
    DISCORD_TOKEN: str = os.getenv('DISCORD_TOKEN', '')
    DISCORD_GUILD_ID: int = int(os.getenv('DISCORD_GUILD_ID', '0') or '0')
    
    # Whisper Configuration (local transcription)
    WHISPER_MODEL_SIZE: str = os.getenv('WHISPER_MODEL_SIZE', 'base')  # tiny, base, small, medium, large-v2, large-v3
    WHISPER_DEVICE: str = os.getenv('WHISPER_DEVICE', 'cpu')  # cpu or cuda
    WHISPER_COMPUTE_TYPE: str = os.getenv('WHISPER_COMPUTE_TYPE', 'int8')  # int8, int8_float16, float16, float32
    
    # Minecraft RCON Configuration
    MINECRAFT_RCON_HOST: str = os.getenv('MINECRAFT_RCON_HOST', 'localhost')
    MINECRAFT_RCON_PORT: int = int(os.getenv('MINECRAFT_RCON_PORT', '25575') or '25575')
    MINECRAFT_RCON_PASSWORD: str = os.getenv('MINECRAFT_RCON_PASSWORD', '')
    
    # Bot Configuration
    DEFAULT_RADIUS: int = int(os.getenv('DEFAULT_RADIUS', '3') or '3')
    MAX_RADIUS: int = int(os.getenv('MAX_RADIUS', '10') or '10')
    COOLDOWN_SECONDS: int = int(os.getenv('COOLDOWN_SECONDS', '5') or '5')
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    CONFIG_DIR: Path = BASE_DIR / 'config'
    BLOCK_WORDS_FILE: Path = CONFIG_DIR / 'block_words.json'
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that required configuration is present."""
        required = [
            cls.DISCORD_TOKEN,
            cls.MINECRAFT_RCON_PASSWORD,
        ]
        return all(required)
    
    @classmethod
    def get_missing_config(cls) -> list[str]:
        """Get list of missing required configuration keys."""
        missing = []
        if not cls.DISCORD_TOKEN:
            missing.append('DISCORD_TOKEN')
        if not cls.MINECRAFT_RCON_PASSWORD:
            missing.append('MINECRAFT_RCON_PASSWORD')
        return missing
