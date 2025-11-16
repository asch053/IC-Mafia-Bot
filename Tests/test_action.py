# Version 6 - No changes needed here, sync with Engine v9 / Narration v8
import unittest
import asyncio
from unittest.mock import Mock, MagicMock, PropertyMock, patch
from collections import defaultdict 

# Add project root to the Python path
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from game.actions import handle_block, handle_heal, handle_kill, handle_investigation

def async_test(f):
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

class TestHandleActions(unittest.TestCase):
    """Unit tests for the action handler functions in game/actions.py"""

    def setUp(self): 
        """Set up a reusable mock game and player environment."""
        self.mock_game = Mock()
        self.mock_game.narration_manager = Mock()
        
        # Ensure the full path exists for the mock
        self.mock_game.bot = MagicMock()
        self.mock_game.bot.loop = MagicMock()
        self.mock_game.bot.loop.create_task = MagicMock()
        
        # --- Mock Roles ---
        mock_role_normal = Mock()
        mock_role_normal.is_night_immune = False
        type(mock_role_normal).investigation_result = PropertyMock(return_value=None) 
        mock_role_normal.name = "Townie"

        mock_role_immune = Mock()
        mock_role_immune.is_night_immune = True
        type(mock_role_immune).investigation_result = PropertyMock(return_value=None)
        mock_role_immune.name = "Godfather"
        
        mock_role_investigate = Mock()
        mock_role_investigate.is_night_immune = False
        type(mock_role_investigate).investigation_result = PropertyMock(return_value={"Suspicious": "This person seems shady."})
        mock_role_investigate.name = "Cop"

        # --- Mock Players ---
        self.player1 = Mock()
        self.player1.display_name = "PlayerOne"
        self.player1.id = 101
        self.player1.role = mock_role_normal
        
        self.player2 = Mock()
        self.player2.display_name = "PlayerTwo"
        self.player2.id = 202
        self.player2.role = mock_role_normal # Default role

        self.player3 = Mock()
        self.player3.display_name = "PlayerThree"
        self.player3.id = 303
        self.player3.role = mock_role_immune 

        self.player4 = Mock()
        self.player4.display_name = "PlayerFour"
        self.player4.id = 404
        self.player4.role = mock_role_investigate 
        
        player_map = {
            101: self.player1,
            202: self.player2,
            303: self.player3,
            404: self.player4,
        }
        self.mock_game.players.get.side_effect = player_map.get
        
        self.mock_game.game_settings = {'game_type': 'classic'}
        
        self.mock_game.narration_manager.reset_mock()
        self.mock_game.bot.loop.create_task.reset_mock() 
        
        self.mock_game.heals_on_players = defaultdict(list)
        self.mock_game.kill_attempts_on = defaultdict(list)
        self.mock_game.blocked_players_this_night = {}


    # --- Tests for handle_kill ---
    
    def test_handle_kill_attempt_success(self):
        night_outcomes = {101: {'status': None}}
        self.mock_game.kill_attempts_on = defaultdict(list) 
        handle_kill(self.mock_game, 101, 202, night_outcomes)
        self.assertIn(101, self.mock_game.kill_attempts_on[202])
        self.mock_game.narration_manager.add_event.assert_not_called()

    def test_handle_kill_attempt_immune(self):
        night_outcomes = {101: {'status': None}}
        self.mock_game.kill_attempts_on = defaultdict(list)
        handle_kill(self.mock_game, 101, 303, night_outcomes)
        self.assertNotIn(101, self.mock_game.kill_attempts_on.get(303, [])) 
        self.mock_game.narration_manager.add_event.assert_called_with( 'kill_immune', killer=self.player1, target=self.player3 )

    def test_handle_kill_self_blocked(self):
        night_outcomes = {101: {'status': 'blocked'}}
        self.mock_game.kill_attempts_on = defaultdict(list)
        handle_kill(self.mock_game, 101, 202, night_outcomes)
        self.assertNotIn(202, self.mock_game.kill_attempts_on)
        self.mock_game.narration_manager.add_event.assert_called_with( 'kill_blocked', killer=self.player1, target=self.player2 )

    # --- Tests for handle_heal ---

    def test_handle_heal_success(self):
        night_outcomes = {101: {'status': None}}
        self.mock_game.heals_on_players = defaultdict(list)
        handle_heal(self.mock_game, 101, 202, night_outcomes)
        self.assertIn(101, self.mock_game.heals_on_players[202])
        self.mock_game.narration_manager.add_event.assert_not_called()

    def test_handle_heal_self_blocked(self):
        night_outcomes = {101: {'status': 'blocked'}}
        self.mock_game.heals_on_players = defaultdict(list)
        handle_heal(self.mock_game, 101, 202, night_outcomes)
        self.assertNotIn(202, self.mock_game.heals_on_players)
        self.mock_game.narration_manager.add_event.assert_not_called()

    # --- Tests for handle_block ---

    def test_handle_block_success(self):
        night_outcomes = {101: {'status': None}, 202: {'status': None}}
        handle_block(self.mock_game, 101, 202, night_outcomes)
        self.assertEqual(night_outcomes[202]['status'], 'blocked')
        self.mock_game.narration_manager.add_event.assert_called_with( 'block', blocker=self.player1, target=self.player2 )

    def test_handle_block_target_action_resolved(self):
        night_outcomes = {101: {'status': None}, 202: {'status': 'successful'}}
        handle_block(self.mock_game, 101, 202, night_outcomes)
        self.assertEqual(night_outcomes[202]['status'], 'successful') 
        self.mock_game.narration_manager.add_event.assert_called_with( 'block_missed', blocker=self.player1, target=self.player2 )

    def test_handle_block_self_blocked(self):
        night_outcomes = {101: {'status': 'blocked'}, 202: {'status': None}}
        handle_block(self.mock_game, 101, 202, night_outcomes)
        self.assertIsNone(night_outcomes[202]['status']) 
        self.mock_game.narration_manager.add_event.assert_not_called()
        #self.mock_game.narration_manager.add_event.assert_called_with( 'block_missed', blocker=self.player1, target=self.player2 )

    # --- Tests for handle_investigation ---
    @patch('game.actions.asyncio.create_task')
    @async_test
    async def test_handle_investigation_success(self, mock_create_task: MagicMock): # <-- ADD ASYNC
        night_outcomes = {101: {'status': None}, 202: {'status': None}}
        handle_investigation(self.mock_game, 101, 202, night_outcomes)
        # Check that our narration event was still added
        self.mock_game.narration_manager.add_event.assert_called_with( 'investigate', investigator=self.player1, target=self.player2 )
        # Check that our NEW mock was called
        mock_create_task.assert_called_once() 
        # --- THIS IS THE KEY FIX ---
        # Get the coroutine that was passed to the mock
        coro = mock_create_task.call_args[0][0]
        self.assertTrue(asyncio.iscoroutine(coro))
        # Now, actually *run* the coroutine to prevent the warning
        await coro

    def test_handle_investigation_self_blocked(self):
        night_outcomes = {101: {'status': 'blocked'}}
        handle_investigation(self.mock_game, 101, 202, night_outcomes)
        self.mock_game.narration_manager.add_event.assert_not_called()
        self.mock_game.bot.loop.create_task.assert_not_called()

    @patch('game.actions.asyncio.create_task')
    @async_test # <-- ADD DECORATOR
    async def test_handle_investigation_special_result(self, mock_create_task: MagicMock): # <-- ADD ASYNC
        night_outcomes = {101: {'status': None}, 404: {'status': None}}
        handle_investigation(self.mock_game, 101, 404, night_outcomes)
        self.mock_game.narration_manager.add_event.assert_called_with( 'investigate', investigator=self.player1, target=self.player4 )
        # Check that our NEW mock was called
        mock_create_task.assert_called_once() 
        # --- THIS IS THE KEY FIX ---
        coro = mock_create_task.call_args[0][0]
        self.assertTrue(asyncio.iscoroutine(coro))
        # Now, actually *run* the coroutine to prevent the warning
        await coro

if __name__ == '__main__':
    unittest.main()


