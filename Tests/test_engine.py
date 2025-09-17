import unittest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from game.engine import Game
from game.player import Player
from game.roles import get_role_instance

# A mock for the config module
sys.modules['config'] = MagicMock(MAX_MISSED_VOTES=2, signup_loop_interval_seconds=15)

# Helper class to mock an async iterator
class AsyncIterator:
    def __init__(self, seq):
        self.iter = iter(seq)
    def __aiter__(self):
        return self
    async def __anext__(self):
        try:
            return next(self.iter)
        except StopIteration:
            raise StopAsyncIteration

class TestGameEngine(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the core game logic in engine.py"""

    def setUp(self):
        """Set up a mock environment for each test."""
        self.mock_bot = Mock()
        
        # --- Configure Mocks Here ---
        self.mock_guild = AsyncMock(name="GuildMock")
        self.mock_user = AsyncMock(name="UserMock")
        self.mock_user.id = 101
        self.mock_user.name = "TestUser"
        self.mock_user.display_name = "TestUser"
        self.mock_user.roles = [] 
        self.mock_channel = AsyncMock(name="ChannelMock")
        
        # Mock synchronous methods with MagicMock
        self.mock_guild.get_member = MagicMock(return_value=self.mock_user)
        self.mock_guild.get_role = MagicMock(return_value=Mock())

        # --- THE FINAL FIX for TypeError ---
        # We replace the async `fetch_members` mock with a synchronous MagicMock
        # that directly returns our async iterator object. This correctly
        # simulates the discord.py library's behavior for an `async for` loop.
        self.mock_guild.fetch_members = MagicMock(return_value=AsyncIterator([self.mock_user]))
        
        # --- Create Game Instance ---
        self.game = Game(self.mock_bot, self.mock_guild)

        # Mock players
        self.player1 = Player(1, "PlayerOne", "PlayerOne")
        self.player2 = Player(2, "PlayerTwo", "PlayerTwo")
        self.player3 = Player(3, "PlayerThree", "PlayerThree")
        
        # Mock roles
        self.townie_role = Mock()
        self.townie_role.name = "Townie"
        self.townie_role.alignment = "Town"
        self.townie_role.is_night_immune = False
        
        self.mafia_role = Mock()
        self.mafia_role.name = "Mafia"
        self.mafia_role.alignment = "Mafia"
        self.mafia_role.is_night_immune = False

    async def test_add_player_during_signup(self):
        """Test that a player can be successfully added during the signup phase."""
        self.game.game_settings["current_phase"] = "signup"
        
        await self.game.add_player(self.mock_user, "TestUser", self.mock_channel)
        
        self.assertIn(101, self.game.players)
        self.assertEqual(self.game.players[101].display_name, "TestUser")
        
        # We can now assert that the async iterator was called
        self.mock_guild.fetch_members.assert_called_once()
        self.mock_user.add_roles.assert_awaited()

    async def test_tally_votes_successful_lynch(self):
        """Test that the correct player is lynched when they have the most votes."""
        self.player1.assign_role(self.townie_role)
        self.player2.assign_role(self.mafia_role)
        self.player3.assign_role(self.townie_role)

        self.game.players = {1: self.player1, 2: self.player2, 3: self.player3}
        
        self.game.lynch_votes = {
            2: [1, 3], # Player2 is voted for by Player1 and Player3
            1: [2]     # Player1 is voted for by Player2
        }
        
        self.game.narration_manager = MagicMock()
        await self.game.tally_votes()

        self.assertFalse(self.game.players[2].is_alive)
        # The test must assert for the event that the code is actually calling.
        self.game.narration_manager.add_event.assert_called_with(
            'lynch', 
            victims=[self.player2], 
            details={self.player2: [self.player1, self.player3]}
        )

