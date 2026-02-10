"""Minecraft RCON client for executing server commands."""
import logging
from typing import List, Optional, Dict
from datetime import datetime

try:
    from mcrcon import MCRcon
except ImportError:
    # Fallback to a basic RCON implementation if mcrcon is not available
    logger = logging.getLogger(__name__)
    logger.warning("mcrcon not available, using basic RCON implementation")
    MCRcon = None

from .config import Config

logger = logging.getLogger(__name__)

# Minecraft Java Edition fill command limit (blocks per command)
FILL_LIMIT_BLOCKS = 32768

# Chunk dimensions and fill limit
# Centered chunk: -8 to +8 in X and Z (17x17); segment height chosen so 17*17*height <= 32768
CHUNK_RADIUS = 8  # chunk extends ~-8 to ~8 around player (17x17 horizontal)
FILL_SEGMENT_HEIGHT = 128  # for 16x16; for 17x17 we use 32768 // (17*17) = 113


class MinecraftRCON:
    """Minecraft RCON client wrapper."""
    
    def __init__(self, host: str, port: int, password: str):
        """Initialize RCON client."""
        self.host = host
        self.port = port
        self.password = password
        self.connection: Optional[MCRcon] = None
        self.connected = False
        self.last_command_time: Dict[str, datetime] = {}
        self.cooldown_seconds = Config.COOLDOWN_SECONDS
    
    def connect(self) -> bool:
        """Connect to the Minecraft server via RCON."""
        try:
            if MCRcon is None:
                logger.error("mcrcon library not installed. Install with: pip install mcrcon")
                return False
            
            self.connection = MCRcon(self.host, self.password, port=self.port)
            self.connection.connect()
            self.connected = True
            logger.info(f"Connected to Minecraft server at {self.host}:{self.port}")
            return True
        except OSError as e:
            # Network errors (connection refused, no route to host, etc.)
            error_msg = str(e)
            if "No route to host" in error_msg or "errno 113" in error_msg.lower():
                logger.warning(
                    f"Cannot reach Minecraft server at {self.host}:{self.port}. "
                    "Check if server is running and firewall allows connections."
                )
            elif "Connection refused" in error_msg or "errno 111" in error_msg.lower():
                logger.warning(
                    f"Minecraft server at {self.host}:{self.port} refused connection. "
                    "Check if RCON is enabled and port is correct."
                )
            else:
                logger.warning(f"Network error connecting to RCON: {e}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Error connecting to RCON: {e}", exc_info=True)
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from the Minecraft server."""
        if self.connection and self.connected:
            try:
                self.connection.disconnect()
                logger.info("Disconnected from Minecraft server")
            except Exception as e:
                logger.error(f"Error disconnecting from RCON: {e}", exc_info=True)
            finally:
                # Always set connected to False, even if disconnect() raised an exception
                self.connected = False
    
    def _check_cooldown(self, user_id: Optional[int] = None) -> bool:
        """Check if enough time has passed since last command."""
        key = f"user_{user_id}" if user_id else "global"
        last_time = self.last_command_time.get(key)
        
        if last_time is None:
            return True
        
        elapsed = (datetime.now() - last_time).total_seconds()
        return elapsed >= self.cooldown_seconds
    
    def _update_cooldown(self, user_id: Optional[int] = None):
        """Update the cooldown timestamp."""
        key = f"user_{user_id}" if user_id else "global"
        self.last_command_time[key] = datetime.now()
    
    def execute_command(self, command: str, user_id: Optional[int] = None, bypass_cooldown: bool = False) -> Optional[str]:
        """
        Execute a command on the Minecraft server.
        
        Args:
            command: Minecraft command to execute
            user_id: User ID for cooldown tracking
            bypass_cooldown: If True, skip cooldown check (for internal operations)
            
        Returns:
            Command response or None if failed
        """
        if not self.connected:
            if not self.connect():
                return None
        
        # Check cooldown (skip for internal operations)
        if not bypass_cooldown and not self._check_cooldown(user_id):
            logger.warning(f"Command blocked by cooldown for user {user_id}")
            return None
        
        try:
            response = self.connection.command(command)
            self._update_cooldown(user_id)
            logger.debug(f"RCON command: {command} -> {response}")
            return response
        except Exception as e:
            logger.error(f"Error executing RCON command '{command}': {e}", exc_info=True)
            # Try to reconnect
            self.connected = False
            if self.connect():
                try:
                    response = self.connection.command(command)
                    self._update_cooldown(user_id)
                    return response
                except Exception as e2:
                    logger.error(f"Error retrying RCON command: {e2}", exc_info=True)
            return None
    
    def get_online_players(self) -> List[str]:
        """
        Get list of online players.
        
        Returns:
            List of player names
        """
        # Bypass cooldown for internal operations
        response = self.execute_command("list", bypass_cooldown=True)
        if not response:
            return []
        
        # Parse response like "There are 2 of a max of 20 players online: player1, player2"
        try:
            # Extract player names from the response
            if ":" in response:
                players_str = response.split(":")[-1].strip()
                if players_str:
                    players = [p.strip() for p in players_str.split(",")]
                    return players
        except Exception as e:
            logger.error(f"Error parsing player list: {e}", exc_info=True)
        
        return []
    
    def replace_blocks_in_chunk_around_player(
        self,
        player: str,
        target_block: str,
        replacement_block: str = "minecraft:air",
        world_min_y: int = -64,
        world_max_y: int = 320,
    ) -> bool:
        """
        Replace a specific block type in a chunk centered on the player (~-8 to ~8 in X and Z),
        breaking into multiple fill commands to stay under the 32,768 block limit.
        
        Chunk is from ~-8 to ~8 in X and Z (all directions around player), full world height.
        Uses relative X/Z and absolute Y.
        
        Args:
            player: Player name
            target_block: Block type to replace (e.g., "minecraft:stone", "minecraft:dirt")
            replacement_block: Block to replace with (default: "minecraft:air" for deletion)
            world_min_y: World bottom Y (e.g. -64 for 1.18+, 0 for older)
            world_max_y: World top Y (e.g. 320 for 1.18+, 255 for older)
            
        Returns:
            True if all fill commands succeeded, False otherwise
        """
        # 17x17 horizontal (from -8 to +8); segment height so 17*17*height <= 32768
        h_blocks = CHUNK_RADIUS * 2 + 1
        segment_height = FILL_LIMIT_BLOCKS // (h_blocks * h_blocks)
        height_span = world_max_y - world_min_y + 1
        num_segments = (height_span + segment_height - 1) // segment_height
        
        for i in range(num_segments):
            y_start = world_min_y + i * segment_height
            y_end = min(world_min_y + (i + 1) * segment_height - 1, world_max_y)
            # execute as <player> at @s run fill ~-8 y_start ~-8 ~8 y_end ~8 <replacement> replace <target>
            command = (
                f"execute as {player} at @s run fill "
                f"~-{CHUNK_RADIUS} {y_start} ~-{CHUNK_RADIUS} ~{CHUNK_RADIUS} {y_end} ~{CHUNK_RADIUS} "
                f"{replacement_block} replace {target_block}"
            )
            response = self.execute_command(command, bypass_cooldown=True)
            # Some servers/RCON libs may return an empty string on success.
            # Treat only None (exception/connection failure) as a failed execution.
            if response is None:
                logger.error(
                    f"Failed to replace {target_block} in chunk segment {i + 1}/{num_segments} "
                    f"around {player} (Y {y_start}-{y_end})"
                )
                return False
        
        logger.info(
            f"Replaced {target_block} with {replacement_block} in chunk (~±{CHUNK_RADIUS}) "
            f"(Y {world_min_y} to {world_max_y}) around {player}"
        )
        return True
    
    def replace_blocks_in_chunk_around_all_players(
        self,
        target_block: str,
        replacement_block: str = "minecraft:air",
        world_min_y: Optional[int] = None,
        world_max_y: Optional[int] = None,
    ) -> Dict[str, bool]:
        """
        Replace a specific block type in a 16x16 chunk around all online players.
        Returns dict of player -> success.
        Uses Config.FILL_WORLD_MIN_Y/MAX_Y if world_min_y/world_max_y not specified.
        """
        if world_min_y is None:
            world_min_y = Config.FILL_WORLD_MIN_Y
        if world_max_y is None:
            world_max_y = Config.FILL_WORLD_MAX_Y
        players = self.get_online_players()
        return {
            player: self.replace_blocks_in_chunk_around_player(
                player, target_block, replacement_block, world_min_y, world_max_y
            )
            for player in players
        }
    
    def test_connection(self) -> bool:
        """Test the RCON connection."""
        response = self.execute_command("list")
        return response is not None
    
    def say(self, message: str, bypass_cooldown: bool = True) -> bool:
        """Broadcast a message to all players on the server (shows as [Server] message)."""
        # Escape quotes in message
        escaped = message.replace('\\', '\\\\').replace('"', '\\"')
        command = f'say "{escaped}"'
        response = self.execute_command(command, bypass_cooldown=bypass_cooldown)
        return response is not None


# Global RCON instance
_rcon_client: Optional[MinecraftRCON] = None


def get_rcon_client() -> MinecraftRCON:
    """Get or create the global RCON client instance."""
    global _rcon_client
    if _rcon_client is None:
        _rcon_client = MinecraftRCON(
            Config.MINECRAFT_RCON_HOST,
            Config.MINECRAFT_RCON_PORT,
            Config.MINECRAFT_RCON_PASSWORD
        )
        _rcon_client.connect()
    return _rcon_client
