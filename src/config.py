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
    # Tuning for quiet Discord voice - adjust if speech is filtered out
    WHISPER_AUDIO_GAIN: float = float(os.getenv('WHISPER_AUDIO_GAIN', '3.0'))  # Amplify audio (1.0=no gain)
    WHISPER_VAD_THRESHOLD: float = float(os.getenv('WHISPER_VAD_THRESHOLD', '0.2'))  # Lower=more sensitive
    WHISPER_LOG_PROB_THRESHOLD: float = float(os.getenv('WHISPER_LOG_PROB_THRESHOLD', '-2.0'))  # More lenient
    WHISPER_NO_SPEECH_THRESHOLD: float = float(os.getenv('WHISPER_NO_SPEECH_THRESHOLD', '0.9'))  # Accept more
    
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
