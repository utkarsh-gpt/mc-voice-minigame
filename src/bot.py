"""Main Discord bot entry point."""
import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .config import Config
from .discord_client import VoiceClient, create_voice_client
from .transcription import get_transcription_service
from .block_detector import get_block_detector
from .minecraft_rcon import get_rcon_client

# Set up logging (DEBUG level, all output to bot.log for debugging)
log_file = Config.BASE_DIR / 'bot.log'
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Log everything (including voice/whisper libs) for debugging
logging.getLogger('discord').setLevel(logging.DEBUG)
logging.getLogger('discord.ext.voice_recv').setLevel(logging.DEBUG)
logging.getLogger('discord.ext.voice_recv.reader').setLevel(logging.DEBUG)
logging.getLogger('discord.ext.voice_recv.opus').setLevel(logging.DEBUG)
logging.getLogger('discord.ext.voice_recv.router').setLevel(logging.DEBUG)
logging.getLogger('faster_whisper').setLevel(logging.DEBUG)
logging.getLogger('httpx').setLevel(logging.DEBUG)


class MinecraftBot(commands.Bot):
    """Main bot class."""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(command_prefix='!', intents=intents)
        
        self.config = Config
        self.custom_voice_clients: dict[int, VoiceClient] = {}
        self.transcribing: dict[int, bool] = {}
        self.transcription_service = get_transcription_service()
        self.block_detector = get_block_detector()
        self.rcon_client = get_rcon_client()
        self.audio_processing_tasks: dict[int, asyncio.Task] = {}
        
        # Set up transcription callback
        self.transcription_service.set_transcript_callback(self._on_transcript)
        # Bias transcription toward Minecraft block names and "clear chunk" command
        block_words = list(self.block_detector.get_block_words().keys()) + ["clear", "chunk"]
        self.transcription_service.set_hotwords(block_words)
    
    async def setup_hook(self):
        """Called when the bot is starting up."""
        logger.info("Setting up bot...")
        
        # Sync commands to guild
        if self.config.DISCORD_GUILD_ID:
            guild = discord.Object(id=self.config.DISCORD_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Synced commands to guild {self.config.DISCORD_GUILD_ID}")
        else:
            await self.tree.sync()
            logger.info("Synced commands globally")
    
    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info(f'{self.user} has logged in!')
        logger.info(f'Bot is in {len(self.guilds)} guild(s)')
        
        # Ensure RCON connection
        if not self.rcon_client.connected:
            logger.info("Attempting to connect to RCON...")
            if self.rcon_client.connect():
                logger.info("RCON connection established")
            else:
                logger.warning("Failed to connect to RCON. Some features may not work.")
    
    async def on_error(self, event, *args, **kwargs):
        """Handle errors."""
        logger.error(f'Error in event {event}', exc_info=True)
    
    async def on_disconnect(self):
        """Called when the bot disconnects."""
        logger.warning("Bot disconnected from Discord. Will attempt to reconnect...")
    
    async def on_resume(self):
        """Called when the bot resumes connection."""
        logger.info("Bot resumed connection to Discord")
        
        # Reconnect RCON if needed
        if not self.rcon_client.connected:
            logger.info("Reconnecting to RCON...")
            self.rcon_client.connect()
    
    async def _on_transcript(self, text: str, user_id: Optional[int] = None, timestamp=None):
        """
        Callback when a transcript is received.
        
        Args:
            text: Transcribed text
            user_id: Discord user ID
            timestamp: Timestamp of transcript
        """
        try:
            # Validate input
            if not text or not text.strip():
                return
            
            # Display what we heard (clear one-line format)
            logger.info(f"Heard: \"{text}\" (user {user_id})")
            
            # Detect block in transcript
            block_info = self.block_detector.detect_block(text, user_id)
            
            if block_info:
                # Only act on "clear chunk" + block: replace that block with air in 16x16 chunk
                normalized = self.block_detector.normalize_text(text)
                if "clear chunk" not in normalized:
                    return
                
                logger.info(f"Block detected: {block_info['block_id']} by user {user_id}")
                
                # Resolve block_id (may be list for e.g. "ore")
                block_id = block_info['block_id']
                if isinstance(block_id, list):
                    block_id = block_id[0] if block_id else None
                if not isinstance(block_id, str) or not block_id.startswith('minecraft:'):
                    logger.error(f"Invalid block_id format: {block_id}")
                    return
                
                if not self.rcon_client.connected:
                    logger.warning("RCON not connected, attempting to reconnect...")
                    if not self.rcon_client.connect():
                        logger.warning(
                            f"RCON connection failed. Block '{block_id}' detected but cannot execute."
                        )
                        return
                
                try:
                    results = self.rcon_client.replace_blocks_in_chunk_around_all_players(
                        target_block=block_id,
                        replacement_block="minecraft:air",
                    )
                    successful_players = [p for p, success in results.items() if success]
                    failed_players = [p for p, success in results.items() if not success]
                    if successful_players:
                        logger.info(f"Cleared {block_id} in chunk for: {', '.join(successful_players)}")
                    if failed_players:
                        logger.warning(f"Failed for: {', '.join(failed_players)}")
                except Exception as e:
                    logger.error(f"Error clearing chunk: {e}", exc_info=True)
                    self.rcon_client.connected = False
                    if self.rcon_client.connect():
                        logger.info("Reconnected to RCON after error")
        except Exception as e:
            logger.error(f"Error in transcript callback: {e}", exc_info=True)
    
    async def _process_audio_loop(self, guild_id: int, voice_client: VoiceClient):
        """Process audio packets in a loop."""
        logger.info(f"Starting audio processing loop for guild {guild_id}")
        
        # Start transcription session
        try:
            await self.transcription_service.start_session()
        except Exception as e:
            logger.error(f"Failed to start transcription session: {e}", exc_info=True)
            return
        
        consecutive_errors = 0
        max_errors = 5
        
        try:
            while self.transcribing.get(guild_id, False) and voice_client.is_capturing_flag:
                try:
                    # Get audio chunk with shorter timeout for faster processing
                    audio_chunk = await voice_client.get_audio_chunk(timeout=0.05)
                    
                    if audio_chunk:
                        # Validate audio chunk
                        audio_data = audio_chunk.get('audio', b'')
                        if not isinstance(audio_data, bytes) or len(audio_data) == 0:
                            continue
                        
                        # Validate PCM data format (should be multiple of 2 bytes for int16)
                        if len(audio_data) % 2 != 0:
                            logger.warning(f"Invalid PCM data length: {len(audio_data)} bytes (not multiple of 2)")
                            continue
                        
                        user_id = audio_chunk.get('user_id')
                        ssrc = audio_chunk.get('ssrc')
                        
                        # Process audio chunk for transcription
                        try:
                            await self.transcription_service.process_audio_chunk(
                                audio_data=audio_data,
                                user_id=user_id,
                                ssrc=ssrc
                            )
                            consecutive_errors = 0  # Reset error counter on success
                        except Exception as e:
                            consecutive_errors += 1
                            logger.error(f"Error processing audio chunk: {e}", exc_info=True)
                            
                            # Stop if too many consecutive errors
                            if consecutive_errors >= max_errors:
                                logger.error(f"Too many consecutive errors ({consecutive_errors}), stopping audio processing")
                                break
                    else:
                        # No audio available, sleep briefly
                        await asyncio.sleep(0.01)
                
                except asyncio.TimeoutError:
                    # Timeout is normal, continue
                    continue
                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"Error in audio loop iteration: {e}", exc_info=True)
                    
                    if consecutive_errors >= max_errors:
                        logger.error(f"Too many consecutive errors ({consecutive_errors}), stopping audio processing")
                        break
                    
                    await asyncio.sleep(1.0)  # Wait longer after error
        
        except asyncio.CancelledError:
            logger.info(f"Audio processing loop cancelled for guild {guild_id}")
        except Exception as e:
            logger.error(f"Fatal error in audio processing loop: {e}", exc_info=True)
        finally:
            # Stop transcription session
            try:
                await self.transcription_service.stop_session()
                await self.transcription_service.flush_buffer()
            except Exception as e:
                logger.error(f"Error stopping transcription session: {e}", exc_info=True)
            
            logger.info(f"Stopped audio processing loop for guild {guild_id}")


# Create bot instance
bot = MinecraftBot()


@bot.tree.command(name='ping', description='Check if the bot is responding')
async def ping(interaction: discord.Interaction):
    """Respond to ping command."""
    await interaction.response.send_message('Pong! Bot is online.', ephemeral=True)


@bot.tree.command(name='join', description='Join your voice channel')
async def join(interaction: discord.Interaction):
    """Join the user's voice channel."""
    if not interaction.user.voice:
        await interaction.response.send_message(
            'You need to be in a voice channel to use this command!',
            ephemeral=True
        )
        return
    
    channel = interaction.user.voice.channel
    
    if interaction.guild.id in bot.custom_voice_clients:
        await interaction.response.send_message(
            f'Already connected to {channel.name}!',
            ephemeral=True
        )
        return
    
    try:
        # Use custom VoiceClient for audio capture
        voice_client = await channel.connect(cls=VoiceClient)
        bot.custom_voice_clients[interaction.guild.id] = voice_client
        bot.transcribing[interaction.guild.id] = False
        await interaction.response.send_message(
            f'Joined {channel.name}!',
            ephemeral=True
        )
        logger.info(f'Joined voice channel: {channel.name} in {interaction.guild.name}')
    except Exception as e:
        logger.error(f'Error joining voice channel: {e}', exc_info=True)
        await interaction.response.send_message(
            'Failed to join voice channel. Check logs for details.',
            ephemeral=True
        )


@bot.tree.command(name='leave', description='Leave the voice channel')
async def leave(interaction: discord.Interaction):
    """Leave the voice channel."""
    if interaction.guild.id not in bot.custom_voice_clients:
        await interaction.response.send_message(
            'Not connected to any voice channel!',
            ephemeral=True
        )
        return
    
    voice_client = bot.custom_voice_clients[interaction.guild.id]
    
    try:
        # Stop capturing before disconnecting
        if isinstance(voice_client, VoiceClient):
            voice_client.stop_capturing()
        await voice_client.disconnect()
        del bot.custom_voice_clients[interaction.guild.id]
        if interaction.guild.id in bot.transcribing:
            del bot.transcribing[interaction.guild.id]
        await interaction.response.send_message(
            'Left the voice channel!',
            ephemeral=True
        )
        logger.info(f'Left voice channel in {interaction.guild.name}')
    except Exception as e:
        logger.error(f'Error leaving voice channel: {e}', exc_info=True)
        await interaction.response.send_message(
            'Failed to leave voice channel. Check logs for details.',
            ephemeral=True
        )


@bot.tree.command(name='start_transcribe', description='Start transcribing audio from voice channel')
async def start_transcribe(interaction: discord.Interaction):
    """Start transcribing audio."""
    if interaction.guild.id not in bot.custom_voice_clients:
        await interaction.response.send_message(
            'Not connected to any voice channel! Use /join first.',
            ephemeral=True
        )
        return
    
    voice_client = bot.custom_voice_clients[interaction.guild.id]
    
    if not isinstance(voice_client, VoiceClient):
        await interaction.response.send_message(
            'Voice client is not configured for transcription!',
            ephemeral=True
        )
        return
    
    if bot.transcribing.get(interaction.guild.id, False):
        await interaction.response.send_message(
            'Already transcribing! Use /stop_transcribe to stop.',
            ephemeral=True
        )
        return
    
    try:
        voice_client.start_capturing()
        bot.transcribing[interaction.guild.id] = True
        
        # Start the audio processing loop
        task = asyncio.create_task(
            bot._process_audio_loop(interaction.guild.id, voice_client)
        )
        bot.audio_processing_tasks[interaction.guild.id] = task
        
        await interaction.response.send_message(
            'Started transcribing audio! Speak Minecraft block names to trigger replacements.',
            ephemeral=True
        )
        logger.info(f'Started transcription in {interaction.guild.name}')
    except Exception as e:
        logger.error(f'Error starting transcription: {e}', exc_info=True)
        bot.transcribing[interaction.guild.id] = False
        voice_client.stop_capturing()
        await interaction.response.send_message(
            'Failed to start transcription. Check logs for details.',
            ephemeral=True
        )


@bot.tree.command(name='stop_transcribe', description='Stop transcribing audio')
async def stop_transcribe(interaction: discord.Interaction):
    """Stop transcribing audio."""
    if interaction.guild.id not in bot.custom_voice_clients:
        await interaction.response.send_message(
            'Not connected to any voice channel!',
            ephemeral=True
        )
        return
    
    voice_client = bot.custom_voice_clients[interaction.guild.id]
    
    if not isinstance(voice_client, VoiceClient):
        await interaction.response.send_message(
            'Voice client is not configured for transcription!',
            ephemeral=True
        )
        return
    
    if not bot.transcribing.get(interaction.guild.id, False):
        await interaction.response.send_message(
            'Not currently transcribing! Use /start_transcribe to start.',
            ephemeral=True
        )
        return
    
    try:
        voice_client.stop_capturing()
        bot.transcribing[interaction.guild.id] = False
        
        # Cancel audio processing task
        if interaction.guild.id in bot.audio_processing_tasks:
            task = bot.audio_processing_tasks[interaction.guild.id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del bot.audio_processing_tasks[interaction.guild.id]
        
        await interaction.response.send_message(
            'Stopped transcribing audio.',
            ephemeral=True
        )
        logger.info(f'Stopped transcription in {interaction.guild.name}')
    except Exception as e:
        logger.error(f'Error stopping transcription: {e}', exc_info=True)
        await interaction.response.send_message(
            'Failed to stop transcription. Check logs for details.',
            ephemeral=True
        )


@bot.tree.command(name='status', description='Show bot status and configuration')
async def status(interaction: discord.Interaction):
    """Show bot status."""
    try:
        # Check voice connection
        voice_connected = interaction.guild.id in bot.custom_voice_clients
        transcribing = bot.transcribing.get(interaction.guild.id, False)
        
        # Check RCON connection
        rcon_connected = bot.rcon_client.connected if bot.rcon_client else False
        
        # Get online players
        online_players = []
        if rcon_connected:
            try:
                online_players = bot.rcon_client.get_online_players()
            except Exception as e:
                logger.error(f"Error getting players: {e}", exc_info=True)
        
        # Get block words count
        block_words = bot.block_detector.get_block_words()
        
        status_message = (
            f"**Bot Status**\n"
            f"Voice Connected: {'✅' if voice_connected else '❌'}\n"
            f"Transcribing: {'✅' if transcribing else '❌'}\n"
            f"RCON Connected: {'✅' if rcon_connected else '❌'}\n"
            f"Online Players: {len(online_players)}\n"
            f"Block Words: {len(block_words)}\n"
            f"Cooldown: {Config.COOLDOWN_SECONDS}s"
        )
        
        if online_players:
            status_message += f"\n\n**Online Players:**\n{', '.join(online_players)}"
        
        await interaction.response.send_message(status_message, ephemeral=True)
    except Exception as e:
        logger.error(f'Error getting status: {e}', exc_info=True)
        await interaction.response.send_message(
            'Failed to get status. Check logs for details.',
            ephemeral=True
        )


@bot.tree.command(name='config_block_words', description='Add or remove block word mappings')
@app_commands.describe(
    action='Add or remove a block word',
    word='Word or phrase to detect',
    block_id='Minecraft block ID (e.g., minecraft:stone)'
)
@app_commands.choices(action=[
    app_commands.Choice(name='add', value='add'),
    app_commands.Choice(name='remove', value='remove'),
    app_commands.Choice(name='list', value='list')
])
async def config_block_words(
    interaction: discord.Interaction,
    action: str,
    word: Optional[str] = None,
    block_id: Optional[str] = None
):
    """Configure block word mappings."""
    # Check permissions
    if not (interaction.user.guild_permissions.administrator or 
            interaction.user.guild_permissions.manage_guild):
        await interaction.response.send_message(
            'You need Administrator or Manage Server permissions to use this command.',
            ephemeral=True
        )
        return
    
    try:
        if action == 'list':
            block_words = bot.block_detector.get_block_words()
            if not block_words:
                await interaction.response.send_message(
                    'No block words configured.',
                    ephemeral=True
                )
                return
            
            words_list = '\n'.join([f"**{w}** → `{b}`" for w, b in block_words.items()])
            await interaction.response.send_message(
                f"**Configured Block Words:**\n{words_list}",
                ephemeral=True
            )
        
        elif action == 'add':
            if not word or not block_id:
                await interaction.response.send_message(
                    'Both word and block_id are required for adding.',
                    ephemeral=True
                )
                return
            
            # Validate inputs
            if not isinstance(word, str) or len(word.strip()) == 0:
                await interaction.response.send_message(
                    'Word must be a non-empty string.',
                    ephemeral=True
                )
                return
            
            if not isinstance(block_id, str) or len(block_id.strip()) == 0:
                await interaction.response.send_message(
                    'Block ID must be a non-empty string.',
                    ephemeral=True
                )
                return
            
            # Validate block_id format
            block_id = block_id.strip().lower()
            if not block_id.startswith('minecraft:'):
                block_id = f'minecraft:{block_id}'
            
            # Basic validation of block_id format
            if not re.match(r'^minecraft:[a-z0-9_]+$', block_id):
                await interaction.response.send_message(
                    'Invalid block ID format. Must be like "minecraft:stone" or "stone".',
                    ephemeral=True
                )
                return
            
            success = bot.block_detector.add_block_word(word.strip().lower(), block_id)
            if success:
                await interaction.response.send_message(
                    f'Added block word: **{word}** → `{block_id}`',
                    ephemeral=True
                )
                logger.info(f'Added block word: {word} -> {block_id} by {interaction.user} ({interaction.user.id})')
            else:
                await interaction.response.send_message(
                    'Failed to add block word. Check logs for details.',
                    ephemeral=True
                )
        
        elif action == 'remove':
            if not word:
                await interaction.response.send_message(
                    'Word is required for removing.',
                    ephemeral=True
                )
                return
            
            success = bot.block_detector.remove_block_word(word)
            if success:
                await interaction.response.send_message(
                    f'Removed block word: **{word}**',
                    ephemeral=True
                )
                logger.info(f'Removed block word: {word} by {interaction.user}')
            else:
                await interaction.response.send_message(
                    f'Block word **{word}** not found.',
                    ephemeral=True
                )
    
    except Exception as e:
        logger.error(f'Error configuring block words: {e}', exc_info=True)
        await interaction.response.send_message(
            'Failed to configure block words. Check logs for details.',
            ephemeral=True
        )


@bot.tree.command(name='toggle_voice_triggers', description='Enable or disable voice triggers for this channel')
@app_commands.describe(enabled='Enable or disable voice triggers')
async def toggle_voice_triggers(interaction: discord.Interaction, enabled: bool):
    """Toggle voice triggers for the current channel."""
    # Check permissions
    if not (interaction.user.guild_permissions.administrator or 
            interaction.user.guild_permissions.manage_guild):
        await interaction.response.send_message(
            'You need Administrator or Manage Server permissions to use this command.',
            ephemeral=True
        )
        return
    
    try:
        # For now, this just controls transcription
        # In a more advanced version, you could have per-channel settings
        if enabled:
            if interaction.guild.id not in bot.custom_voice_clients:
                await interaction.response.send_message(
                    'Bot must be connected to a voice channel first. Use /join.',
                    ephemeral=True
                )
                return
            
            if not bot.transcribing.get(interaction.guild.id, False):
                await interaction.response.send_message(
                    'Use /start_transcribe to enable transcription.',
                    ephemeral=True
                )
                return
            
            await interaction.response.send_message(
                'Voice triggers enabled. Say e.g. "grass clear chunk" to clear that block in a chunk.',
                ephemeral=True
            )
        else:
            if bot.transcribing.get(interaction.guild.id, False):
                await interaction.response.send_message(
                    'Use /stop_transcribe to disable transcription.',
                    ephemeral=True
                )
                return
            
            await interaction.response.send_message(
                'Voice triggers are disabled.',
                ephemeral=True
            )
        
        logger.info(f'Voice triggers toggled to {enabled} by {interaction.user}')
    except Exception as e:
        logger.error(f'Error toggling voice triggers: {e}', exc_info=True)
        await interaction.response.send_message(
            'Failed to toggle voice triggers. Check logs for details.',
            ephemeral=True
        )


def main():
    """Main entry point."""
    # Validate configuration
    if not Config.validate():
        missing = Config.get_missing_config()
        logger.error(f'Missing required configuration: {", ".join(missing)}')
        logger.error('Please check your .env file and ensure all required values are set.')
        sys.exit(1)
    
    # Run the bot
    try:
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info('Bot stopped by user')
    except Exception as e:
        logger.error(f'Fatal error: {e}', exc_info=True)
        sys.exit(1)


if __name__ == '__main__' or __name__ == 'src.bot':
    main()
