import unittest
from unittest.mock import Mock, MagicMock, PropertyMock

# Add project root to the Python path
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from game.actions import handle_block, handle_heal, handle_kill, handle_investigation

class TestHandleActions(unittest.TestCase):
    """Unit tests for the action handler functions in game/actions.py"""

    def setUp(self):
        """Set up a reusable mock game and player environment."""
        self.mock_game = Mock()
        self.mock_game.narration_manager = Mock()
        
        # --- Mock Roles ---
        # It's crucial that the mock roles have all the attributes the functions will check.
        mock_role_normal = Mock()
        mock_role_normal.is_night_immune = False
        mock_role_normal.investigation_result = None

        mock_role_immune = Mock()
        mock_role_immune.is_night_immune = True
        mock_role_immune.investigation_result = None
        
        # --- Mock Players ---
        self.player1 = Mock()
        self.player1.display_name = "PlayerOne"
        self.player1.id = 101
        self.player1.role = mock_role_normal
        
        self.player2 = Mock()
        self.player2.display_name = "PlayerTwo"
        self.player2.id = 202
        self.player2.role = mock_role_normal

        self.player3 = Mock()
        self.player3.display_name = "PlayerThree"
        self.player3.id = 303
        self.player3.role = mock_role_immune # This player is immune
        
        # This allows self.mock_game.players.get(id) to return the correct player mock
        self.mock_game.players.get.side_effect = lambda player_id: {
            101: self.player1,
            202: self.player2,
            303: self.player3,
        }.get(player_id)
        
        self.mock_game.game_settings = {'game_type': 'classic'}
        # Reset these for every test to ensure isolation
        self.mock_game.heals_on_players = {}
        self.mock_game.kill_attempts_on = {}
        self.mock_game.blocked_players_this_night = {}

    # --- Tests for handle_kill ---
    
    def test_handle_kill_attempt_success(self):
        """Test a successful kill attempt is recorded."""
        night_outcomes = {101: {'status': None}}
        self.mock_game.kill_attempts_on = {} # Ensure it starts empty
        
        handle_kill(self.mock_game, 101, 202, night_outcomes)
        
        # Assert that the victim's ID was added to the list of kill attempts
        self.assertIn(202, self.mock_game.kill_attempts_on)
        self.assertEqual(self.mock_game.kill_attempts_on[202], [101])
        self.assertEqual(night_outcomes[101]['status'], 'successful')

