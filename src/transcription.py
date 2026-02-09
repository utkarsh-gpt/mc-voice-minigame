"""Speech-to-text transcription using Faster-Whisper (local)."""
import asyncio
import io
import logging
import wave
from pathlib import Path
from typing import Optional, Callable, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from faster_whisper import WhisperModel

from .config import Config

logger = logging.getLogger(__name__)

# Discord voice sends PCM at 48kHz; Whisper expects 16kHz
DISCORD_PCM_RATE = 48000
WHISPER_SAMPLE_RATE = 16000
# Resample ratio: 48k -> 16k = 1/3 (take every 3rd sample)
RESAMPLE_RATIO = DISCORD_PCM_RATE // WHISPER_SAMPLE_RATE  # 3


class TranscriptionService:
    """Service for real-time speech-to-text transcription using Faster-Whisper."""
    
    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        """
        Initialize the transcription service.
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v2, large-v3)
                       Smaller = faster but less accurate. 'base' is a good balance.
            device: Device to use ('cpu' or 'cuda' for GPU)
            compute_type: Compute type ('int8', 'int8_float16', 'float16', 'float32')
                         'int8' is fastest on CPU, 'float16' is best for GPU
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model: Optional[WhisperModel] = None
        self.is_transcribing = False
        self.transcript_callback: Optional[Callable] = None
        self.audio_buffer: bytes = b''
        self.user_id_map: Dict[int, int] = {}  # SSRC -> User ID
        self.hotwords: str = ""  # Bias model toward these terms (e.g. Minecraft block names)
        self._recording_dir: Optional[Path] = None
        self._chunk_counter: int = 0
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="whisper")
        self._model_lock = asyncio.Lock()
    
    def _load_model(self):
        """Load the Whisper model (lazy loading)."""
        if self.model is None:
            logger.info(f"Loading Faster-Whisper model: {self.model_size} on {self.device}")
            try:
                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type
                )
                logger.info("Faster-Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Error loading Whisper model: {e}", exc_info=True)
                raise
    
    def set_transcript_callback(self, callback: Callable):
        """Set callback function for when transcripts are received."""
        self.transcript_callback = callback
    
    def set_hotwords(self, words: list) -> None:
        """Set hotwords to bias transcription (e.g. block names for Minecraft)."""
        self.hotwords = " ".join(str(w).lower() for w in words) if words else ""
    
    async def start_session(self, sample_rate: int = 16000):
        """Start a new transcription session."""
        if self.is_transcribing:
            logger.warning("Transcription session already active")
            return
        
        try:
            # Load model if not already loaded
            async with self._model_lock:
                if self.model is None:
                    # Run model loading in executor to avoid blocking
                    await asyncio.get_event_loop().run_in_executor(
                        self.executor, self._load_model
                    )
            
            self.is_transcribing = True
            self.audio_buffer = b''
            self._chunk_counter = 0
            # Create recording directory if saving audio
            if getattr(Config, 'SAVE_AUDIO', False):
                self._recording_dir = Config.SAVE_AUDIO_DIR
                self._recording_dir.mkdir(parents=True, exist_ok=True)
                session_name = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                self._recording_dir = self._recording_dir / session_name
                self._recording_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Saving audio to {self._recording_dir}")
            else:
                self._recording_dir = None
            logger.info("Started transcription session")
        except Exception as e:
            logger.error(f"Error starting transcription session: {e}", exc_info=True)
            self.is_transcribing = False
            raise
    
    async def stop_session(self):
        """Stop the transcription session."""
        if not self.is_transcribing:
            return
        
        self.is_transcribing = False
        self.audio_buffer = b''
        self._recording_dir = None
        logger.info("Stopped transcription session")
    
    def _save_audio_chunk(self, pcm_48k: bytes, user_id: Optional[int] = None) -> None:
        """Save a PCM chunk to a WAV file (48kHz mono 16-bit)."""
        if not self._recording_dir:
            return
        try:
            self._chunk_counter += 1
            user_suffix = f"_user{user_id}" if user_id else ""
            wav_path = self._recording_dir / f"chunk_{self._chunk_counter:04d}{user_suffix}.wav"
            with wave.open(str(wav_path), 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(DISCORD_PCM_RATE)
                wf.writeframes(pcm_48k)
        except Exception as e:
            logger.warning(f"Failed to save audio chunk: {e}")
    
    def _resample_48k_to_16k(self, pcm_48k: bytes) -> bytes:
        """Resample PCM16 48kHz mono to 16kHz by decimating (take every 3rd sample)."""
        if len(pcm_48k) < 2:
            return b''
        arr = np.frombuffer(pcm_48k, dtype=np.int16)
        # Decimate: 48k -> 16k = 1/3 samples
        decimated = arr[::RESAMPLE_RATIO].copy()
        return decimated.tobytes()

    async def process_audio_chunk(self, audio_data: bytes, user_id: Optional[int] = None, ssrc: Optional[int] = None):
        """
        Process an audio chunk and get transcription.
        
        Args:
            audio_data: Raw audio bytes (PCM16 mono 48kHz from Discord)
            user_id: Discord user ID
            ssrc: SSRC identifier
        """
        if not self.is_transcribing:
            return
        
        # Map SSRC to user ID if provided
        if ssrc and user_id:
            self.user_id_map[ssrc] = user_id
        
        # Buffer audio data (Discord sends 48kHz PCM)
        self.audio_buffer += audio_data
        
        # Process in chunks (longer = more context for accuracy, but more latency)
        chunk_secs = getattr(Config, 'WHISPER_CHUNK_SECONDS', 3)
        chunk_48k_bytes = DISCORD_PCM_RATE * chunk_secs * 2  # PCM16
        
        if len(self.audio_buffer) >= chunk_48k_bytes:
            chunk_48k = self.audio_buffer[:chunk_48k_bytes]
            self.audio_buffer = self.audio_buffer[chunk_48k_bytes:]
            
            # Save to WAV file if recording is enabled
            if self._recording_dir:
                self._save_audio_chunk(chunk_48k, user_id)
            
            # Resample 48kHz -> 16kHz for Whisper
            chunk_16k = self._resample_48k_to_16k(chunk_48k)
            if len(chunk_16k) == 0:
                return
            
            # Process chunk asynchronously
            asyncio.create_task(self._transcribe_chunk(chunk_16k, user_id))
    
    def _bytes_to_numpy(self, audio_bytes: bytes, sample_rate: int = 16000) -> np.ndarray:
        """Convert PCM16 bytes to numpy array, with optional gain for quiet Discord audio."""
        if len(audio_bytes) == 0:
            return np.array([], dtype=np.float32)
        
        # Ensure we have even number of bytes for int16
        if len(audio_bytes) % 2 != 0:
            audio_bytes = audio_bytes[:-1]  # Drop last byte if odd
        
        # Convert bytes to int16 array
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Convert to float32 and normalize to [-1.0, 1.0]
        audio_float = audio_array.astype(np.float32) / 32768.0
        
        # Apply gain - Discord voice can be very quiet; amplify to improve VAD/transcription
        gain = getattr(Config, 'WHISPER_AUDIO_GAIN', 3.0)
        if gain != 1.0:
            audio_float = audio_float * gain
            audio_float = np.clip(audio_float, -1.0, 1.0)
        
        return audio_float
    
    async def _transcribe_chunk(self, audio_data: bytes, user_id: Optional[int]):
        """Transcribe an audio chunk using Faster-Whisper."""
        try:
            # Ensure model is loaded
            if self.model is None:
                async with self._model_lock:
                    if self.model is None:
                        await asyncio.get_event_loop().run_in_executor(
                            self.executor, self._load_model
                        )
            
            # Convert bytes to numpy array
            audio_numpy = self._bytes_to_numpy(audio_data)
            
            if len(audio_numpy) == 0:
                logger.debug("Skipping empty audio chunk")
                return
            
            # Log audio stats for debugging
            audio_rms = np.sqrt(np.mean(audio_numpy**2)) if len(audio_numpy) > 0 else 0.0
            logger.debug(f"Processing audio chunk: {len(audio_data)} bytes, {len(audio_numpy)} samples, RMS: {audio_rms:.4f}")
            
            # Run transcription in executor to avoid blocking event loop
            segments, info = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._run_transcription,
                audio_numpy
            )
            
            # Combine segments into full text
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())
            
            text = " ".join(text_parts).strip()
            
            if text and self.transcript_callback:
                await self.transcript_callback(
                    text=text,
                    user_id=user_id,
                    timestamp=datetime.now()
                )
                # Bot logs "Heard: ..." in callback; avoid duplicate log here
            elif not text:
                logger.debug(f"No speech in chunk (VAD filtered, User: {user_id})")
            
        except Exception as e:
            logger.error(f"Error transcribing audio chunk: {e}", exc_info=True)
    
    def _run_transcription(self, audio_numpy: np.ndarray):
        """Run transcription (called in executor)."""
        # Validate audio array
        if len(audio_numpy) == 0:
            logger.warning("Empty audio array provided for transcription")
            return [], None
        
        # Check if audio is all zeros (silence)
        if np.all(audio_numpy == 0):
            logger.debug("Audio array contains only silence")
            return [], None
        
        # Use Faster-Whisper's transcribe method (audio must be 16kHz mono float32)
        # beam_size=5 improves accuracy; hotwords bias toward Minecraft block names
        vad_threshold = getattr(Config, 'WHISPER_VAD_THRESHOLD', 0.2)
        log_prob_threshold = getattr(Config, 'WHISPER_LOG_PROB_THRESHOLD', -1.5)
        no_speech_threshold = getattr(Config, 'WHISPER_NO_SPEECH_THRESHOLD', 0.7)
        beam_size = getattr(Config, 'WHISPER_BEAM_SIZE', 5)
        hotwords = self.hotwords or None  # Biases model toward block names, "clear chunk"
        segments, info = self.model.transcribe(
            audio_numpy,
            language="en",
            beam_size=beam_size,  # 5 = more accurate, 1 = faster
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=200,
                threshold=vad_threshold,
                min_speech_duration_ms=100,
                speech_pad_ms=300,
            ),
            log_prob_threshold=log_prob_threshold,
            no_speech_threshold=no_speech_threshold,
            hotwords=hotwords,
        )
        
        # Convert generator to list
        return list(segments), info
    
    async def flush_buffer(self):
        """Flush remaining audio buffer and transcribe."""
        if self.audio_buffer and self.is_transcribing:
            # Process remaining buffer
            await self._transcribe_chunk(self.audio_buffer, None)
            self.audio_buffer = b''


# Global transcription service instance
_transcription_service: Optional[TranscriptionService] = None


def get_transcription_service() -> TranscriptionService:
    """Get or create the global transcription service instance."""
    global _transcription_service
    if _transcription_service is None:
        # Get model size from config or use default
        model_size = getattr(Config, 'WHISPER_MODEL_SIZE', 'base')
        device = getattr(Config, 'WHISPER_DEVICE', 'cpu')
        compute_type = getattr(Config, 'WHISPER_COMPUTE_TYPE', 'int8')
        
        _transcription_service = TranscriptionService(
            model_size=model_size,
            device=device,
            compute_type=compute_type
        )
    return _transcription_service
