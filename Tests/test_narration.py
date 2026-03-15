# Version with Console Logging
import unittest
import asyncio
from unittest.mock import Mock, MagicMock, PropertyMock, patch
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
    """Unit tests for the action handler functions in game/actions.py"""

    def setUp(self): 
        print(f"\n[ACTION TEST] Setting up {self._testMethodName}...")
        self.mock_game = Mock()
        self.mock_game.narration_manager = Mock()
        
        self.mock_game.bot = MagicMock()
        self.mock_game.bot.loop = MagicMock()
        self.mock_game.bot.loop.create_task = MagicMock()
        
        # --- Mock Roles ---
        mock_role_normal = Mock(name="Townie", is_night_immune=False)
        type(mock_role_normal).investigation_result = PropertyMock(return_value=None) 

        mock_role_immune = Mock(name="Godfather", is_night_immune=True)
        type(mock_role_immune).investigation_result = PropertyMock(return_value=None) 

        mock_role_special = Mock(name="Framer", is_night_immune=False)
        type(mock_role_special).investigation_result = PropertyMock(return_value="Townie") 
        
        # --- Mock Players ---
        self.player1 = Mock(id=101, display_name="PlayerOne", role=mock_role_normal)
        self.player2 = Mock(id=202, display_name="PlayerTwo", role=mock_role_normal)
        self.player3 = Mock(id=303, display_name="PlayerThree", role=mock_role_immune)
        self.player4 = Mock(id=404, display_name="PlayerFour", role=mock_role_special)
        
        self.mock_game.players = {
            101: self.player1,
            202: self.player2,
            303: self.player3,
            404: self.player4,
        }

    # --- Tests for handle_kill ---
        
    def test_handle_kill_success(self):
        print("   -> Testing successful kill...")
        night_outcomes = {101: {'status': None}, 202: {'status': None}}
        handle_kill(self.mock_game, 101, 202, night_outcomes)
        
        self.assertEqual(night_outcomes[202]['status'], 'killed')
        self.mock_game.narration_manager.add_event.assert_called_with( 'kill', killer=self.player1, victim=self.player2 )
        print("   -> Success: Victim marked as killed.")

    def test_handle_kill_blocked(self):
        print("   -> Testing blocked kill...")
        night_outcomes = {101: {'status': 'blocked'}, 202: {'status': None}}
        handle_kill(self.mock_game, 101, 202, night_outcomes)
        
        self.assertIsNone(night_outcomes[202]['status'])
        self.mock_game.narration_manager.add_event.assert_not_called()
        print("   -> Success: Kill prevented by block.")

    def test_handle_kill_target_immune(self):
        print("   -> Testing kill on immune target...")
        night_outcomes = {101: {'status': None}, 303: {'status': None}}
        handle_kill(self.mock_game, 101, 303, night_outcomes)
        
        self.assertIsNone(night_outcomes[303]['status']) 
        self.mock_game.narration_manager.add_event.assert_called_with( 'kill_immune', killer=self.player1, victim=self.player3 )
        print("   -> Success: Target survived due to immunity.")

    def test_handle_kill_target_healed(self):
        print("   -> Testing kill on healed target...")
        night_outcomes = {101: {'status': None}, 202: {'status': 'healed'}}
        handle_kill(self.mock_game, 101, 202, night_outcomes)
        
        self.assertEqual(night_outcomes[202]['status'], 'healed') 
        self.mock_game.narration_manager.add_event.assert_called_with( 'kill_healed', killer=self.player1, victim=self.player2 )
        print("   -> Success: Target survived due to healing.")

    # --- Tests for handle_heal ---

    def test_handle_heal_success(self):
        print("   -> Testing successful heal...")
        night_outcomes = {101: {'status': None}, 202: {'status': None}}
        handle_heal(self.mock_game, 101, 202, night_outcomes)
        self.assertEqual(night_outcomes[202]['status'], 'healed')
        self.mock_game.narration_manager.add_event.assert_called_with( 'heal', doctor=self.player1, target=self.player2 )
        print("   -> Success: Target marked as healed.")

    def test_handle_heal_self_blocked(self):
        print("   -> Testing blocked heal...")
        night_outcomes = {101: {'status': 'blocked'}, 202: {'status': None}}
        handle_heal(self.mock_game, 101, 202, night_outcomes)
        self.assertIsNone(night_outcomes[202]['status'])
        self.mock_game.narration_manager.add_event.assert_not_called()
        print("   -> Success: Heal prevented.")

    def test_handle_heal_target_already_healed(self):
        print("   -> Testing double heal (should remain healed)...")
        night_outcomes = {101: {'status': None}, 202: {'status': 'healed'}}
        handle_heal(self.mock_game, 101, 202, night_outcomes)
        self.assertEqual(night_outcomes[202]['status'], 'healed') 
        self.mock_game.narration_manager.add_event.assert_called_with( 'heal', doctor=self.player1, target=self.player2 )
        print("   -> Success: Status maintained.")

    # --- Tests for handle_block ---
        
    def test_handle_block_success(self):
        print("   -> Testing successful block...")
        night_outcomes = {101: {'status': None}, 202: {'status': None}}
        handle_block(self.mock_game, 101, 202, night_outcomes)
        self.assertEqual(night_outcomes[202]['status'], 'blocked')
        self.mock_game.narration_manager.add_event.assert_called_with( 'block', blocker=self.player1, target=self.player2 )
        print("   -> Success: Target marked as blocked.")

    def test_handle_block_self_blocked(self):
        print("   -> Testing blocker getting blocked...")
        night_outcomes = {101: {'status': 'blocked'}, 202: {'status': None}}
        handle_block(self.mock_game, 101, 202, night_outcomes)
        self.assertIsNone(night_outcomes[202]['status']) 
        self.mock_game.narration_manager.add_event.assert_not_called()
        print("   -> Success: Block action prevented.")

    # --- Tests for handle_investigation ---

    @patch('game.actions.asyncio.create_task')
    @async_test 
    async def test_handle_investigation_success(self, mock_create_task): 
        print("   -> Testing investigation...")
        night_outcomes = {101: {'status': None}, 202: {'status': None}}
        handle_investigation(self.mock_game, 101, 202, night_outcomes)

        self.mock_game.narration_manager.add_event.assert_called_with( 'investigate', investigator=self.player1, target=self.player2 )
        
        mock_create_task.assert_called_once() 
        coro = mock_create_task.call_args[0][0]
        await coro
        print("   -> Success: Investigation DM task created.")

    def test_handle_investigation_self_blocked(self):
        print("   -> Testing blocked investigation...")
        night_outcomes = {101: {'status': 'blocked'}, 202: {'status': None}}
        handle_investigation(self.mock_game, 101, 202, night_outcomes)
        self.mock_game.narration_manager.add_event.assert_not_called()
        self.mock_game.bot.loop.create_task.assert_not_called() 
        print("   -> Success: No investigation occurred.")

    @patch('game.actions.asyncio.create_task')
    @async_test 
    async def test_handle_investigation_special_result(self, mock_create_task):
        print("   -> Testing special investigation (Framer)...")
        night_outcomes = {101: {'status': None}, 404: {'status': None}}
        handle_investigation(self.mock_game, 101, 404, night_outcomes)
        self.mock_game.narration_manager.add_event.assert_called_with( 'investigate', investigator=self.player1, target=self.player4 )
        
        mock_create_task.assert_called_once() 
        coro = mock_create_task.call_args[0][0]
        await coro
        print("   -> Success: DM sent with special result.")