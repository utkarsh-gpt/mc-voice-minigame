# Discord Bot Setup Guide

Complete step-by-step guide to set up your Discord bot for the Minecraft Voice Transcription Bot.

## Step 1: Create a Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click the **"New Application"** button (top right)
3. Give your application a name (e.g., "Minecraft Voice Bot")
4. Click **"Create"**

## Step 2: Create the Bot

1. In your application, go to the **"Bot"** section (left sidebar)
2. Click **"Add Bot"** or **"Reset Token"** if you already have a bot
3. Click **"Yes, do it!"** to confirm
4. **IMPORTANT**: Copy the bot token immediately (you'll need this for `.env`)
   - Click **"Reset Token"** if you need to regenerate it
   - ⚠️ **Never share your bot token publicly!**

## Step 3: Configure Bot Settings

In the **"Bot"** section:

1. **Bot Username**: Set a name (e.g., "Minecraft Voice Bot")
2. **Icon**: Upload a bot icon (optional)
3. **Public Bot**: Leave this **UNCHECKED** (unless you want others to add it)
4. **Requires OAuth2 Code Grant**: Leave this **UNCHECKED**

### Enable Privileged Gateway Intents

Scroll down to **"Privileged Gateway Intents"** and enable:

- ✅ **MESSAGE CONTENT INTENT** (Required for reading messages)
- ✅ **SERVER MEMBERS INTENT** (Optional, but recommended)

Click **"Save Changes"** after enabling intents.

## Step 4: Set Up OAuth2 URL (Invite Bot)

1. Go to the **"OAuth2"** section (left sidebar)
2. Click **"URL Generator"** submenu
3. Under **"SCOPES"**, select:

   - ✅ `bot`
   - ✅ `applications.commands` (for slash commands)
4. Under **"BOT PERMISSIONS"**, select:

   - ✅ **View Channels** (Required)
   - ✅ **Connect** (Required - to join voice channels)
   - ✅ **Speak** (Required - to receive audio)
   - ✅ **Use Voice Activity** (Required - to capture voice)
   - ✅ **Send Messages** (Optional - for status messages)
   - ✅ **Use Slash Commands** (Optional - for slash commands)
5. **Copy the generated URL** at the bottom (looks like:

   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=...&scope=bot%20applications.commands
   ```

## Step 5: Invite Bot to Your Server

1. Open the copied OAuth2 URL in your browser
2. Select the Discord server you want to add the bot to
3. Click **"Authorize"**
4. Complete any CAPTCHA if prompted
5. The bot should now appear in your server's member list (offline)

## Step 6: Configure Bot Permissions in Server

1. Go to your Discord server
2. Right-click your server name → **"Server Settings"**
3. Go to **"Roles"** → Find your bot's role
4. Or go to **"Members"** → Find your bot → Right-click → **"Roles"**
5. Ensure the bot has permissions to:
   - Access the voice channel you want to use
   - Send messages (if you want status updates)

### Alternative: Channel-Specific Permissions

1. Right-click the voice channel → **"Edit Channel"**
2. Go to **"Permissions"** tab
3. Add your bot (or its role)
4. Enable:
   - ✅ **View Channel**
   - ✅ **Connect**
   - ✅ **Speak**
   - ✅ **Use Voice Activity**

## Step 7: Get Your Server ID (Optional)

If you want to sync commands to a specific server:

1. Enable **Developer Mode** in Discord:
   - User Settings → Advanced → Enable Developer Mode
2. Right-click your server name → **"Copy Server ID"**
3. Add this to your `.env` file as `DISCORD_GUILD_ID`

## Step 8: Add Credentials to .env File

1. Copy `.env.example` to `.env`:

   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and add:

   ```env
   DISCORD_TOKEN=your_bot_token_here
   DISCORD_GUILD_ID=your_server_id_here  # Optional but recommended
   ```

## Verification Checklist

- [X] Bot created in Developer Portal
- [X] Bot token copied to `.env` file
- [X] Message Content Intent enabled
- [X] Bot invited to server via OAuth2 URL
- [X] Bot has voice channel permissions
- [X] Bot appears in server member list
- [X] `.env` file configured with token

## Troubleshooting

### Bot doesn't appear in server

- Check that you completed the OAuth2 authorization
- Verify you have "Manage Server" permission in the server

### Bot can't join voice channel

- Check bot has "Connect" and "Speak" permissions
- Verify bot role is above the voice channel in role hierarchy
- Check channel-specific permissions

### Slash commands don't appear

- Wait a few minutes for commands to sync (up to 1 hour for global)
- Use `/ping` to test if commands are working
- Check that `applications.commands` scope was selected in OAuth2

### "Missing Access" or Permission Errors

- Ensure bot role has necessary permissions
- Check server role hierarchy (bot role should be high enough)
- Verify channel-specific permissions

## Security Notes

⚠️ **Important Security Practices:**

1. **Never commit `.env` file** - It contains your bot token
2. **Never share your bot token** - Anyone with it can control your bot
3. **Regenerate token if compromised** - Use "Reset Token" in Developer Portal
4. **Use minimal permissions** - Only grant what the bot needs
5. **Keep bot private** - Unless you want others to invite it

## Next Steps

Once your bot is set up:

1. Run the bot: `python -m src.bot`
2. Test with `/ping` command
3. Join a voice channel and use `/join`
4. Start transcription with `/start_transcribe`

Your bot should now be ready to use!
