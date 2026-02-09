#!/usr/bin/env python3
"""Demo script to send a grass block replacement command via RCON."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.minecraft_rcon import get_rcon_client
from src.config import Config

def main():
    """Send grass block replacement command to all online players."""
    print("🌱 Grass Block Replacement Demo")
    print("=" * 50)
    
    # Get RCON client
    print(f"Connecting to RCON at {Config.MINECRAFT_RCON_HOST}:{Config.MINECRAFT_RCON_PORT}...")
    rcon_client = get_rcon_client()
    
    if not rcon_client.connected:
        print("❌ Failed to connect to RCON server!")
        print("Please check:")
        print(f"  - Server is running at {Config.MINECRAFT_RCON_HOST}:{Config.MINECRAFT_RCON_PORT}")
        print(f"  - RCON is enabled in server.properties")
        print(f"  - Password matches: {Config.MINECRAFT_RCON_PASSWORD[:3]}***")
        return 1
    
    print("✅ Connected to RCON server!")
    
    # Get online players
    print("\n📋 Getting online players...")
    players = rcon_client.get_online_players()
    
    if not players:
        print("⚠️  No players are currently online.")
        print("The command will still be sent, but there are no players to affect.")
    else:
        print(f"✅ Found {len(players)} online player(s): {', '.join(players)}")
    
    # Send grass block replacement command
    print(f"\n🌱 Sending grass block replacement command...")
    print(f"   Block: minecraft:grass_block")
    print(f"   Radius: {Config.DEFAULT_RADIUS} blocks")
    print(f"   Target: All online players")
    
    results = rcon_client.replace_blocks_around_all_players(
        block_id="minecraft:grass_block",
        radius=Config.DEFAULT_RADIUS
    )
    
    # Display results
    print("\n📊 Results:")
    print("=" * 50)
    
    if not results:
        print("⚠️  No players were affected (no players online)")
    else:
        for player, success in results.items():
            status = "✅ Success" if success else "❌ Failed"
            print(f"  {player}: {status}")
    
    # Disconnect
    rcon_client.disconnect()
    print("\n✅ Demo completed!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
