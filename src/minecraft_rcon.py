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
    
    def replace_blocks_around_player(self, player: str, block_id: str, radius: int, target_block: str = "minecraft:air") -> bool:
        """
        Replace blocks around a player.
        
        Args:
            player: Player name
            block_id: Block ID to place (e.g., "minecraft:stone")
            radius: Radius around player
            target_block: Block to replace (default: air)
            
        Returns:
            True if successful, False otherwise
        """
        # Clamp radius to max
        radius = min(radius, Config.MAX_RADIUS)
        
        # Build the fill command
        # execute as <player> at @s run fill ~-r ~-1 ~-r ~r ~r ~r <block> replace <target>
        command = (
            f"execute as {player} at @s run fill "
            f"~-{radius} ~-1 ~-{radius} "
            f"~{radius} ~{radius} ~{radius} "
            f"{block_id} replace {target_block}"
        )
        
        # Bypass cooldown for internal operations (called from replace_blocks_around_all_players)
        response = self.execute_command(command, bypass_cooldown=True)
        
        if response:
            logger.info(f"Replaced blocks around {player} with {block_id} (radius: {radius})")
            return True
        else:
            logger.error(f"Failed to replace blocks around {player}")
            return False
    
    def replace_blocks_around_all_players(self, block_id: str, radius: int, target_block: str = "minecraft:air") -> Dict[str, bool]:
        """
        Replace blocks around all online players.
        
        Args:
            block_id: Block ID to place
            radius: Radius around each player
            target_block: Block to replace
            
        Returns:
            Dictionary mapping player names to success status
        """
        players = self.get_online_players()
        results = {}
        
        for player in players:
            success = self.replace_blocks_around_player(player, block_id, radius, target_block)
            results[player] = success
        
        return results
    
    def test_connection(self) -> bool:
        """Test the RCON connection."""
        response = self.execute_command("list")
        return response is not None
    
    def say(self, message: str) -> bool:
        """Send a message to all players."""
        # Escape quotes in message
        message = message.replace('"', '\\"')
        command = f'say "{message}"'
        response = self.execute_command(command)
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
