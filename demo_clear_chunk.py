#!/usr/bin/env python3
"""Demo: delete a specific block type in a 16x16 chunk around each online player."""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.minecraft_rcon import get_rcon_client
from src.config import Config

def main():
    if len(sys.argv) > 1:
        target_block = sys.argv[1]
    else:
        target_block = "minecraft:stone"  # Default: delete stone blocks
    
    print(f"Delete {target_block} in 16x16 chunk around players")
    print("=" * 50)
    rcon = get_rcon_client()
    if not rcon.connected:
        print("Failed to connect to RCON")
        return 1
    print("Connected to RCON")
    players = rcon.get_online_players()
    if not players:
        print("No players online")
        rcon.disconnect()
        return 0
    print(f"Online: {', '.join(players)}")
    # Replace target_block with air in a 16x16 chunk (full world height)
    # Uses multiple fill commands to stay under 32k limit
    results = rcon.replace_blocks_in_chunk_around_all_players(
        target_block=target_block,
        replacement_block="minecraft:air",
        world_min_y=-64,
        world_max_y=320
    )
    for p, ok in results.items():
        print(f"  {p}: {'OK' if ok else 'Failed'}")
    rcon.disconnect()
    print("Done.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
