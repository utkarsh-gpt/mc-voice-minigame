"""Discord voice client for audio capture."""
import asyncio
import logging
from typing import Optional

import discord
from discord.ext import voice_recv

logger = logging.getLogger(__name__)

# Monkey-patch to handle occasional OpusError "corrupted stream" from Discord voice packets.
# Without this, a single corrupted packet crashes the packet router and stops listening.
_OPUS_SILENCE_FRAME = (
    b'\x00' * (discord.opus.Decoder.SAMPLES_PER_FRAME * discord.opus.Decoder.CHANNELS * 2)
)


def _decode_packet_robust(self, packet):
    """Wrapper that catches OpusError and returns silence instead of crashing."""
    try:
        return self._decode_packet_original(packet)
    except discord.opus.OpusError as e:
        logger.warning("Discord voice: corrupted Opus packet, substituting silence: %s", e)
        return packet, _OPUS_SILENCE_FRAME


# Apply patch to PacketDecoder
_from_opus = voice_recv.opus
_from_opus.PacketDecoder._decode_packet_original = _from_opus.PacketDecoder._decode_packet
_from_opus.PacketDecoder._decode_packet = _decode_packet_robust


class AudioQueueSink(voice_recv.AudioSink):
    """Custom sink that queues audio data for processing."""
    
    def __init__(self, audio_queue: asyncio.Queue, is_capturing_flag):
        super().__init__()
        self.audio_queue = audio_queue
        self.is_capturing_flag = is_capturing_flag
    
    def wants_opus(self) -> bool:
        """We want PCM decoded audio, not Opus."""
        return False
    
    def write(self, user: Optional[discord.User], data: voice_recv.VoiceData) -> None:
        """Called when audio data is received."""
        if not self.is_capturing_flag[0]:
            return
        
        # Get user ID
        user_id = user.id if user else None
        
        # Get SSRC from packet if available
        ssrc = None
        if data.packet:
            ssrc = getattr(data.packet, 'ssrc', None)
        
        # Queue audio data for processing
        audio_data = {
            'ssrc': ssrc,
            'user_id': user_id,
            'audio': data.pcm,  # Use decoded PCM data
            'timestamp': getattr(data.packet, 'timestamp', None) if data.packet else None
        }
        
        # Validate PCM data before queuing
        if not data.pcm or len(data.pcm) == 0:
            return
        
        try:
            self.audio_queue.put_nowait(audio_data)
        except asyncio.QueueFull:
            # If queue is full, try to drop oldest item and add new one
            try:
                # Remove one old item
                self.audio_queue.get_nowait()
                # Add new item
                self.audio_queue.put_nowait(audio_data)
                logger.debug("Audio queue full, dropped oldest packet")
            except asyncio.QueueEmpty:
                # Queue became empty, just add
                try:
                    self.audio_queue.put_nowait(audio_data)
                except asyncio.QueueFull:
                    logger.warning("Audio queue is full, dropping packet")
    
    def cleanup(self) -> None:
        """Cleanup when sink is stopped."""
        pass


class VoiceClient(voice_recv.VoiceRecvClient):
    """Extended voice client that captures audio packets."""
    
    def __init__(self, client, channel):
        super().__init__(client, channel)
        # Queue with larger maxsize to handle burst audio (about 30 seconds of audio at 20ms packets)
        # Discord sends ~50 packets/second, so 1500 = ~30 seconds buffer
        self.audio_queue: asyncio.Queue = asyncio.Queue(maxsize=1500)
        self.is_capturing = [False]  # Use list to allow reference passing
        self._sink: Optional[AudioQueueSink] = None
    
    def start_capturing(self):
        """Start capturing audio packets."""
        if self.is_capturing[0]:
            logger.debug("Already capturing audio")
            return
        
        self.is_capturing[0] = True
        
        # Create and start listening with sink if not already listening
        if not self.is_listening():
            if not self.is_connected():
                logger.warning("Cannot start capturing: not connected to voice channel")
                self.is_capturing[0] = False
                return
            
            self._sink = AudioQueueSink(self.audio_queue, self.is_capturing)
            try:
                self.listen(self._sink)
            except discord.ClientException as e:
                logger.error(f"Failed to start listening: {e}")
                self.is_capturing[0] = False
                raise
        
        logger.info("Started capturing audio")
    
    def stop_capturing(self):
        """Stop capturing audio packets."""
        self.is_capturing[0] = False
        # Stop listening if we're listening
        if self.is_listening():
            self.stop_listening()
        logger.info("Stopped capturing audio")
    
    @property
    def is_capturing_flag(self) -> bool:
        """Check if currently capturing audio."""
        return self.is_capturing[0]
    
    async def get_audio_chunk(self, timeout: float = 1.0) -> Optional[dict]:
        """Get the next audio chunk from the queue."""
        try:
            return await asyncio.wait_for(self.audio_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


async def convert_audio_to_pcm16(audio_data: bytes, sample_rate: int = 16000) -> bytes:
    """
    Convert Discord Opus audio to PCM16 mono format.
    
    Discord sends Opus-encoded audio. This function converts it to PCM16
    mono at the specified sample rate for STT APIs.
    
    Note: This is a placeholder. Actual conversion requires opus decoding.
    For production, use pydub or similar library with proper Opus decoder.
    """
    # TODO: Implement proper Opus to PCM16 conversion
    # For now, return the audio data as-is (will need proper decoder)
    # In production, use: pydub with opus codec or discord.py's built-in decoder
    return audio_data


def create_voice_client(client: discord.Client, channel: discord.VoiceChannel) -> VoiceClient:
    """Create and return a voice client for the given channel."""
    return VoiceClient(client, channel)
