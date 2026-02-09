<<<<<<< HEAD
# mc-voice-minigame
=======
# Discord Minecraft Voice Transcription Bot

A Discord bot that joins voice channels, transcribes audio in real-time, detects Minecraft block names in speech, and uses RCON to replace blocks around players on a Minecraft server.

## Features

- 🎤 Real-time voice transcription using Faster-Whisper (local, no API needed)
- 🎮 Automatic Minecraft block replacement via RCON
- 🔊 Voice-activated block commands
- ⚙️ Configurable block word mappings
- 🛡️ Rate limiting and safety features
- ⚡ Fast local transcription (no internet required)

## Prerequisites

- Python 3.10 or higher
- Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))
- Minecraft server with RCON enabled
- (Optional) NVIDIA GPU with CUDA for faster transcription

## Discord Bot Setup

**📖 For detailed step-by-step instructions, see [DISCORD_SETUP.md](DISCORD_SETUP.md)**

Quick summary:

1. **Create Application & Bot**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create new application → Go to "Bot" section → Create bot
   - Copy bot token → Add to `.env` as `DISCORD_TOKEN`

2. **Enable Intents**
   - In Bot section, enable **"Message Content Intent"** (under Privileged Gateway Intents)

3. **Generate Invite URL**
   - Go to "OAuth2" → "URL Generator"
   - Select scopes: `bot`, `applications.commands`
   - Select permissions: `Connect`, `Speak`, `Use Voice Activity`, `View Channels`
   - Copy URL and invite bot to your server

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd mc-app
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/Mac:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. **Configure block words**
   Edit `config/block_words.json` to add/remove block word mappings.

6. **Enable RCON on your Minecraft server**
   Edit `server.properties`:
   ```
   enable-rcon=true
   rcon.port=25575
   rcon.password=your_secure_password
   ```

7. **Run the bot**
   ```bash
   python -m src.bot
   ```

## Usage

### Discord Commands

- `/ping` - Check if the bot is responding
- `/join` - Join your voice channel
- `/leave` - Leave the voice channel
- `/start_transcribe` - Start transcribing audio
- `/stop_transcribe` - Stop transcribing audio
- `/status` - Show bot status
- `/set_radius <number>` - Set default replacement radius
- `/config_block_words` - Configure tracked block words

### How It Works

1. Invite the bot to your Discord server with voice permissions
2. Use `/join` to have the bot join your voice channel
3. Use `/start_transcribe` to begin transcription
4. Speak Minecraft block names (e.g., "stone", "diamond block")
5. The bot detects the block name and replaces blocks around all players on your Minecraft server

## Configuration

### Block Words

Edit `config/block_words.json` to customize which words trigger block replacements:

```json
{
  "stone": "minecraft:stone",
  "diamond block": "minecraft:diamond_block",
  "dirt": "minecraft:dirt"
}
```

### Environment Variables

See `.env.example` for all available configuration options.

## Troubleshooting

- **Bot won't join voice channel**: 
  - Ensure the bot has "Connect" and "Speak" permissions in the voice channel
  - Check that you're in a voice channel when using `/join`
  
- **No transcription**: 
  - Verify transcription is started with `/start_transcribe`
  - Check bot logs for transcription errors
  - First run will download the Whisper model (one-time download)
  - For faster transcription, use GPU by setting `WHISPER_DEVICE=cuda` in `.env`
  - Try a smaller model (e.g., `tiny` or `base`) for faster processing
  
- **RCON connection fails**: 
  - Verify RCON is enabled in `server.properties` and server is restarted
  - Check that RCON credentials in `.env` match your server configuration
  - Ensure firewall allows connections to RCON port (default: 25575)
  
- **Blocks don't change**: 
  - Check Minecraft server logs for RCON command errors
  - Verify players are online when block words are spoken
  - Check that block words are correctly configured in `config/block_words.json`
  - Use `/status` to check RCON connection status

## Notes

- **Transcription**: Uses Faster-Whisper for local transcription (no API costs!)
  - First run downloads the model (~150MB for 'base' model)
  - Model size affects speed vs accuracy: `tiny` (fastest) → `base` → `small` → `medium` → `large-v3` (most accurate)
  - GPU support: Set `WHISPER_DEVICE=cuda` and `WHISPER_COMPUTE_TYPE=float16` for GPU acceleration
- The bot processes audio in ~2 second chunks for transcription
- Block replacements have a cooldown (default: 5 seconds) to prevent spam
- Maximum replacement radius is configurable (default: 10 blocks)
- All actions are logged to `bot.log` for debugging

## License

MIT
>>>>>>> fa0c837 (init)
