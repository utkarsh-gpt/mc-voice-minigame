# Minecraft Voice Bot

A Discord bot that listens in voice channels, transcribes what you say, and clears Minecraft blocks by name. Say **"stone"**, **"cobblestone"**, or **"ore"** and the bot uses RCON to replace those blocks with air in the chunk around each online player.

---

## Features

- **Voice transcription** — Joins a Discord voice channel and transcribes speech locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (no external API).
- **Block-by-voice** — When a configured block word is detected in the transcript, the bot runs RCON commands to clear that block type in the chunk around all players.
- **Configurable block words** — Map phrases (e.g. "stone", "ore", "wood") to block IDs or tags via `config/block_words.json` or the `/config_block_words` slash command.
- **Slash commands** — `/join`, `/leave`, `/start_transcribe`, `/stop_transcribe`, `/status`, `/ping`, and optional block-word management.

---

## Prerequisites

- **Python 3.10+**
- **Discord bot** — Create an application and bot in the [Discord Developer Portal](https://discord.com/developers/applications). See [DISCORD_SETUP.md](DISCORD_SETUP.md) for step-by-step setup.
- **Minecraft server with RCON** — Java Edition server with RCON enabled (e.g. `enable-rcon=true`, `rcon.port=25575`, `rcon.password=...` in `server.properties`).

---

## Installation

```bash
# Clone the repository (or use your existing copy)
git clone <your-repo-url>
cd mc-app

# Create a virtual environment (recommended)
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Configuration

1. Copy the example env file and edit it:

   ```bash
   cp .env.example .env
   ```

2. Set these **required** variables in `.env`:

   | Variable | Description |
   |----------|-------------|
   | `DISCORD_TOKEN` | Your Discord bot token from the Developer Portal |
   | `MINECRAFT_RCON_PASSWORD` | RCON password from `server.properties` |

3. Optional but recommended:

   | Variable | Description |
   |----------|-------------|
   | `DISCORD_GUILD_ID` | Your Discord server ID (for faster slash-command sync) |
   | `MINECRAFT_RCON_HOST` | RCON host (default: `localhost`) |
   | `MINECRAFT_RCON_PORT` | RCON port (default: `25575`) |
   | `WHISPER_MODEL_SIZE` | `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3` (default: `base`) |
   | `WHISPER_DEVICE` | `cpu` or `cuda` (default: `cpu`) |
   | `COOLDOWN_SECONDS` | Cooldown between voice-triggered clears (default: `5`) |

See `.env.example` for all options (Whisper tuning, audio gain, VAD, etc.).

---

## Minecraft RCON Setup

In your Minecraft server directory, edit `server.properties`:

```properties
enable-rcon=true
rcon.port=25575
rcon.password=your_secure_password
```

Restart the server, then set `MINECRAFT_RCON_PASSWORD` in `.env` to the same password. If the server is on another machine, set `MINECRAFT_RCON_HOST` accordingly.

---

## Running the Bot

```bash
python -m src
# or
python -m src.bot
```

Once the bot is online:

1. Invite it to your server (see [DISCORD_SETUP.md](DISCORD_SETUP.md)).
2. Join a voice channel and use **`/join`** so the bot joins.
3. Use **`/start_transcribe`** to begin listening.
4. Say a block name (e.g. "stone", "cobblestone", "ore"). The bot will clear that block in the chunk around each player and announce it in-game via RCON `say`.

Use **`/stop_transcribe`** to stop listening and **`/leave`** to disconnect the bot from the channel.

---

## Discord Commands

| Command | Description |
|--------|-------------|
| `/ping` | Check if the bot is online |
| `/join` | Bot joins your current voice channel |
| `/leave` | Bot leaves the voice channel |
| `/start_transcribe` | Start transcribing and listening for block words |
| `/stop_transcribe` | Stop transcribing |
| `/status` | Show voice connection, transcription, RCON, online players, block words count |
| `/config_block_words` | Add/remove/list block word mappings (admin/manage server) |
| `/toggle_voice_triggers` | Enable/disable voice triggers (admin/manage server) |

---

## Block Words

Block words are phrases that, when detected in the transcript, trigger a clear of the corresponding block(s). They are stored in `config/block_words.json` and can be edited there or via `/config_block_words add|remove|list`.

- **Single block:** `"cobblestone": "minecraft:cobblestone"`
- **Multiple blocks (e.g. stone variants):** `"stone": ["minecraft:stone", "minecraft:deepslate", ...]`
- **Tags:** `"wood": "#minecraft:planks"` or `"log": "#minecraft:logs"`

The bot uses these mappings to run RCON `fill` (or equivalent) to replace matching blocks with air in the chunk around each player.

---

## Project Structure

```
mc-app/
├── config/
│   ├── block_words.json   # Block phrase → block ID/tag mappings
│   └── server_config.json
├── src/
│   ├── bot.py             # Discord bot, slash commands, transcript callback
│   ├── config.py          # Loads .env and exposes Config
│   ├── discord_client.py  # Voice client with audio capture
│   ├── transcription.py   # faster-whisper session and processing
│   ├── block_detector.py  # Match transcript text to block words
│   └── minecraft_rcon.py  # RCON client and chunk clear logic
├── tests/
├── .env.example
├── requirements.txt
├── DISCORD_SETUP.md       # Detailed Discord bot creation and invite
└── README.md
```

---

## Development

- Run tests: `pytest` (see `pytest.ini` and `tests/`).
- Logs are written to `bot.log` and stdout; log level is DEBUG by default for troubleshooting.

---

## License

Use and modify as you like. If you redistribute, consider keeping attribution.
