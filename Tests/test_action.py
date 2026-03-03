# Updated Tests/test_action.py
import unittest
import asyncio
from unittest.mock import Mock, MagicMock, PropertyMock, patch, AsyncMock
from collections import defaultdict 

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Game.actions import handle_block, handle_heal, handle_kill, handle_investigation

def async_test(f):
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

class TestHandleActions(unittest.TestCase):
    def setUp(self): 
        # Using MagicMock allows for subscripting (game.game_settings["key"])
        self.mock_game = MagicMock()
        self.mock_game.narration_manager = MagicMock()
        self.mock_game.bot = MagicMock()
        
        # CRITICAL FIX: These MUST be real dicts for the code to iterate/assign to them
        self.mock_game.kill_attempts_on = {}
        self.mock_game.heals_on_players = {}
        self.mock_game.blocked_players_this_night = {} 
        self.mock_game.game_settings = {"game_type": "classic"}
        
        # Setup Player Mocks
        self.player1 = Mock(id=101, display_name="P1", is_alive=True)
        self.player1.role = Mock(is_night_immune=False, investigation_immune=False, name="Townie")
        self.player1.send_dm = AsyncMock()

        self.player2 = Mock(id=202, display_name="P2", is_alive=True)
        self.player2.role = Mock(is_night_immune=False, investigation_immune=False, name="Doctor")
        self.player2.send_dm = AsyncMock()

        self.player3 = Mock(id=303, display_name="P3", is_alive=True)
        self.player3.role = Mock(is_night_immune=True, investigation_immune=True, name="Godfather")
        self.player3.send_dm = AsyncMock()

        self.mock_game.players = {101: self.player1, 202: self.player2, 303: self.player3}

    # --- handle_kill Tests ---
        
    def test_handle_kill_success(self):
        night_outcomes = {101: {'status': None}}
        handle_kill(self.mock_game, 101, 202, night_outcomes)
        
        # Your code marks the killer's status as 'successful'
        self.assertEqual(night_outcomes[101]['status'], 'successful')
        # It records the attempt in kill_attempts_on
        self.assertIn(101, self.mock_game.kill_attempts_on[202])

    def test_handle_kill_target_immune(self):
        night_outcomes = {101: {'status': None}}
        handle_kill(self.mock_game, 101, 303, night_outcomes)
        
        # Verify call uses 'target' not 'victim'
        self.mock_game.narration_manager.add_event.assert_called_with(
            'kill_immune', killer=self.player1, target=self.player3
        )
        self.assertNotIn(303, self.mock_game.kill_attempts_on)

    # --- handle_heal Tests ---

    def test_handle_heal_success(self):
        night_outcomes = {202: {'status': None}}
        handle_heal(self.mock_game, 202, 101, night_outcomes)
        
        self.assertEqual(night_outcomes[202]['status'], 'successful')
        self.assertIn(202, self.mock_game.heals_on_players[101])

    # --- handle_block Tests ---

    def test_handle_block_success(self):
        # Target (101) must have status None to be blocked
        night_outcomes = {202: {'status': None}, 101: {'status': None}}
        handle_block(self.mock_game, 202, 101, night_outcomes)
        
        self.assertEqual(night_outcomes[101]['status'], 'blocked')
        self.assertEqual(self.mock_game.blocked_players_this_night[101], 202)

    # --- handle_investigation Tests ---

    @patch('game.actions.asyncio.create_task')
    @async_test
    async def test_handle_investigation_success(self, mock_create_task):
        night_outcomes = {101: {'status': None}}
        # Silencing coroutine warning
        mock_create_task.side_effect = lambda coro: coro.close() 

        handle_investigation(self.mock_game, 101, 202, night_outcomes)
        
        self.assertEqual(night_outcomes[101]['status'], 'successful')
        mock_create_task.assert_called_once()
        self.mock_game.narration_manager.add_event.assert_called_with(
            'investigate', investigator=self.player1, target=self.player2
        )

if __name__ == '__main__':
    unittest.main()