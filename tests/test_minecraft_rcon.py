"""Tests for Minecraft RCON client."""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to path and import as package
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.minecraft_rcon import MinecraftRCON


class TestMinecraftRCON:
    """Test cases for MinecraftRCON class."""
    
    @pytest.fixture
    def mock_mcrcon(self):
        """Create a mock MCRcon instance."""
        mock_rcon = Mock()
        mock_rcon.connect = Mock()
        mock_rcon.disconnect = Mock()
        mock_rcon.command = Mock(return_value="Command executed successfully")
        return mock_rcon
    
    @pytest.fixture
    def rcon_client(self):
        """Create a MinecraftRCON instance for testing."""
        return MinecraftRCON(
            host="test.example.com",
            port=25575,
            password="test_password"
        )
    
    def test_init(self, rcon_client):
        """Test RCON client initialization."""
        assert rcon_client.host == "test.example.com"
        assert rcon_client.port == 25575
        assert rcon_client.password == "test_password"
        assert rcon_client.connected is False
        assert rcon_client.connection is None
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_connect_success(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test successful RCON connection."""
        mock_mcrcon_class.return_value = mock_mcrcon
        mock_mcrcon.connect.return_value = None  # connect() doesn't return anything
        
        result = rcon_client.connect()
        
        assert result is True
        assert rcon_client.connected is True
        assert rcon_client.connection == mock_mcrcon
        mock_mcrcon_class.assert_called_once_with("test.example.com", "test_password", port=25575)
        mock_mcrcon.connect.assert_called_once()
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_connect_no_route_to_host(self, mock_mcrcon_class, rcon_client):
        """Test connection failure with 'No route to host' error."""
        mock_mcrcon_class.side_effect = OSError("[Errno 113] No route to host")
        
        result = rcon_client.connect()
        
        assert result is False
        assert rcon_client.connected is False
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_connect_connection_refused(self, mock_mcrcon_class, rcon_client):
        """Test connection failure with 'Connection refused' error."""
        mock_mcrcon_class.side_effect = OSError("[Errno 111] Connection refused")
        
        result = rcon_client.connect()
        
        assert result is False
        assert rcon_client.connected is False
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_connect_generic_error(self, mock_mcrcon_class, rcon_client):
        """Test connection failure with generic error."""
        mock_mcrcon_class.side_effect = Exception("Generic connection error")
        
        result = rcon_client.connect()
        
        assert result is False
        assert rcon_client.connected is False
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_connect_mcrcon_not_available(self, mock_mcrcon_class, rcon_client):
        """Test connection when mcrcon library is not available."""
        with patch('src.minecraft_rcon.MCRcon', None):
            result = rcon_client.connect()
            assert result is False
    
    def test_disconnect_success(self, rcon_client, mock_mcrcon):
        """Test successful disconnection."""
        rcon_client.connection = mock_mcrcon
        rcon_client.connected = True
        
        rcon_client.disconnect()
        
        assert rcon_client.connected is False
        mock_mcrcon.disconnect.assert_called_once()
    
    def test_disconnect_not_connected(self, rcon_client):
        """Test disconnect when not connected."""
        rcon_client.connected = False
        rcon_client.connection = None
        
        # Should not raise an error
        rcon_client.disconnect()
        assert rcon_client.connected is False
    
    def test_disconnect_error(self, rcon_client, mock_mcrcon):
        """Test disconnect with error."""
        rcon_client.connection = mock_mcrcon
        rcon_client.connected = True
        mock_mcrcon.disconnect.side_effect = Exception("Disconnect error")
        
        # Should handle error gracefully
        rcon_client.disconnect()
        assert rcon_client.connected is False
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_execute_command_success(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test successful command execution."""
        mock_mcrcon_class.return_value = mock_mcrcon
        rcon_client.connect()
        
        result = rcon_client.execute_command("list", user_id=123)
        
        assert result == "Command executed successfully"
        mock_mcrcon.command.assert_called_once_with("list")
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_execute_command_not_connected(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test command execution when not connected."""
        mock_mcrcon_class.return_value = mock_mcrcon
        rcon_client.connected = False
        
        result = rcon_client.execute_command("list")
        
        # Should attempt to connect first
        assert mock_mcrcon_class.called
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_execute_command_cooldown(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test command execution blocked by cooldown."""
        mock_mcrcon_class.return_value = mock_mcrcon
        rcon_client.connect()
        rcon_client.cooldown_seconds = 5
        
        # Execute first command
        rcon_client.execute_command("list", user_id=123)
        
        # Try to execute again immediately (should be blocked)
        result = rcon_client.execute_command("list", user_id=123)
        
        assert result is None
        # Should only be called once (first execution)
        assert mock_mcrcon.command.call_count == 1
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_execute_command_cooldown_expired(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test command execution after cooldown expires."""
        mock_mcrcon_class.return_value = mock_mcrcon
        rcon_client.connect()
        rcon_client.cooldown_seconds = 0.1  # Very short cooldown
        
        # Execute first command
        rcon_client.execute_command("list", user_id=123)
        
        # Wait for cooldown to expire
        import time
        time.sleep(0.15)
        
        # Execute again (should succeed)
        result = rcon_client.execute_command("list", user_id=123)
        
        assert result == "Command executed successfully"
        assert mock_mcrcon.command.call_count == 2
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_execute_command_reconnect_on_error(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test automatic reconnection on command error."""
        mock_mcrcon_class.return_value = mock_mcrcon
        rcon_client.connect()
        
        # First call fails, second succeeds
        mock_mcrcon.command.side_effect = [
            Exception("Connection lost"),
            "Command executed successfully"
        ]
        
        result = rcon_client.execute_command("list")
        
        assert result == "Command executed successfully"
        assert mock_mcrcon.command.call_count == 2
        # Should have reconnected
        assert mock_mcrcon.connect.call_count == 2
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_get_online_players(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test getting online players list."""
        mock_mcrcon_class.return_value = mock_mcrcon
        mock_mcrcon.command.return_value = "There are 2 of a max of 20 players online: Player1, Player2"
        rcon_client.connect()
        
        players = rcon_client.get_online_players()
        
        assert players == ["Player1", "Player2"]
        mock_mcrcon.command.assert_called_once_with("list")
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_get_online_players_empty(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test getting online players when no players are online."""
        mock_mcrcon_class.return_value = mock_mcrcon
        mock_mcrcon.command.return_value = "There are 0 of a max of 20 players online:"
        rcon_client.connect()
        
        players = rcon_client.get_online_players()
        
        assert players == []
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_get_online_players_failed(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test getting online players when command fails."""
        mock_mcrcon_class.return_value = mock_mcrcon
        mock_mcrcon.command.return_value = None
        rcon_client.connect()
        
        players = rcon_client.get_online_players()
        
        assert players == []
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_replace_blocks_around_player(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test replacing blocks around a player."""
        mock_mcrcon_class.return_value = mock_mcrcon
        mock_mcrcon.command.return_value = "Successfully filled 100 blocks"
        rcon_client.connect()
        
        result = rcon_client.replace_blocks_around_player(
            player="TestPlayer",
            block_id="minecraft:stone",
            radius=3
        )
        
        assert result is True
        mock_mcrcon.command.assert_called_once()
        call_args = mock_mcrcon.command.call_args[0][0]
        assert "execute as TestPlayer" in call_args
        assert "minecraft:stone" in call_args
        assert "replace minecraft:air" in call_args
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_replace_blocks_around_player_radius_clamped(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test that radius is clamped to MAX_RADIUS."""
        from src.config import Config
        mock_mcrcon_class.return_value = mock_mcrcon
        mock_mcrcon.command.return_value = "Success"
        rcon_client.connect()
        
        # Try with radius larger than MAX_RADIUS
        rcon_client.replace_blocks_around_player(
            player="TestPlayer",
            block_id="minecraft:stone",
            radius=999  # Much larger than MAX_RADIUS
        )
        
        call_args = mock_mcrcon.command.call_args[0][0]
        # Should contain clamped radius
        assert f"~-{Config.MAX_RADIUS}" in call_args
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_replace_blocks_around_all_players(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test replacing blocks around all players."""
        mock_mcrcon_class.return_value = mock_mcrcon
        # First call returns player list, subsequent calls return success
        mock_mcrcon.command.side_effect = [
            "There are 2 of a max of 20 players online: Player1, Player2",
            "Successfully filled 50 blocks",
            "Successfully filled 50 blocks"
        ]
        rcon_client.connect()
        
        results = rcon_client.replace_blocks_around_all_players(
            block_id="minecraft:stone",
            radius=3
        )
        
        assert results == {"Player1": True, "Player2": True}
        assert mock_mcrcon.command.call_count == 3  # list + 2 replacements
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_replace_blocks_around_all_players_no_players(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test replacing blocks when no players are online."""
        mock_mcrcon_class.return_value = mock_mcrcon
        mock_mcrcon.command.return_value = "There are 0 of a max of 20 players online:"
        rcon_client.connect()
        
        results = rcon_client.replace_blocks_around_all_players(
            block_id="minecraft:stone",
            radius=3
        )
        
        assert results == {}
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_test_connection(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test connection test method."""
        mock_mcrcon_class.return_value = mock_mcrcon
        mock_mcrcon.command.return_value = "There are 0 players online"
        rcon_client.connect()
        
        result = rcon_client.test_connection()
        
        assert result is True
        mock_mcrcon.command.assert_called_once_with("list")
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_test_connection_failed(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test connection test when it fails."""
        mock_mcrcon_class.return_value = mock_mcrcon
        mock_mcrcon.command.return_value = None
        rcon_client.connect()
        
        result = rcon_client.test_connection()
        
        assert result is False
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_say(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test sending a message to all players."""
        mock_mcrcon_class.return_value = mock_mcrcon
        mock_mcrcon.command.return_value = "Message sent"
        rcon_client.connect()
        
        result = rcon_client.say("Hello, players!")
        
        assert result is True
        mock_mcrcon.command.assert_called_once()
        call_args = mock_mcrcon.command.call_args[0][0]
        assert 'say "Hello, players!"' in call_args
    
    @patch('src.minecraft_rcon.MCRcon')
    def test_say_with_quotes(self, mock_mcrcon_class, rcon_client, mock_mcrcon):
        """Test sending a message with quotes (should be escaped)."""
        mock_mcrcon_class.return_value = mock_mcrcon
        mock_mcrcon.command.return_value = "Message sent"
        rcon_client.connect()
        
        result = rcon_client.say('Say "hello" to everyone')
        
        assert result is True
        call_args = mock_mcrcon.command.call_args[0][0]
        assert '\\"' in call_args  # Quotes should be escaped


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
