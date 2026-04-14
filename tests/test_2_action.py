import unittest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 1. MUST BE FIRST: Load logger & environment mocks
from tests.test_0_logging import setup_test_logging
logger = setup_test_logging()

from game.actions import handle_block, handle_heal, handle_kill, handle_investigation

class TestHandleActions(unittest.IsolatedAsyncioTestCase):
    def setUp(self): 
        self.mock_game = MagicMock()
        self.mock_game.narration_manager = MagicMock()
        self.mock_game.bot = MagicMock()
        
        self.mock_game.kill_attempts_on = {}
        self.mock_game.heals_on_players = {}
        self.mock_game.blocked_players_this_night = {} 
        self.mock_game.game_settings = {"game_type": "classic"}
        
        # Player 1 (Townie), Player 2 (Doctor), Player 3 (Godfather - Immune)
        self.player1 = Mock(id=101, display_name="P1", is_alive=True)
        self.player1.role = Mock(is_night_immune=False, investigation_immune=False, name="Townie")
        self.player2 = Mock(id=202, display_name="P2", is_alive=True)
        self.player2.role = Mock(is_night_immune=False, investigation_immune=False, name="Doctor")
        self.player3 = Mock(id=303, display_name="P3", is_alive=True)
        self.player3.role = Mock(is_night_immune=True, investigation_immune=True, name="Godfather")
        
        self.mock_game.players = {101: self.player1, 202: self.player2, 303: self.player3}

    def test_handle_kill_success(self):
        msg = f"[START] {self._testMethodName} - Testing normal kill processing"
        print(f"\n{msg}"); logger.info(msg)
        
        night_outcomes = {101: {'status': None}, 202: {'status': None}}
        
        action_msg = "[ACTION] Executing handle_kill (101 -> 202)"
        print(action_msg); logger.info(action_msg)
        
        handle_kill(self.mock_game, 101, 202, night_outcomes)
        
        self.assertEqual(night_outcomes[202]['status'], 'killed')
        self.mock_game.narration_manager.add_event.assert_called_with('kill', killer=self.player1, victim=self.player2)
        
        outcome_msg = "[OUTCOME] Success! Status set to 'killed' and narration event 'kill' created."
        print(outcome_msg); logger.info(outcome_msg)

    def test_handle_kill_target_immune(self):
        msg = f"[START] {self._testMethodName} - Testing kill against immune target"
        print(f"\n{msg}"); logger.info(msg)
        
        night_outcomes = {101: {'status': None}, 303: {'status': None}}
        
        action_msg = "[ACTION] Executing handle_kill (101 -> Immune 303)"
        print(action_msg); logger.info(action_msg)
        
        handle_kill(self.mock_game, 101, 303, night_outcomes)
        
        self.mock_game.narration_manager.add_event.assert_called_with('kill_immune', killer=self.player1, victim=self.player3)
        self.assertIsNone(night_outcomes[303]['status'])
        
        outcome_msg = "[OUTCOME] Success! Target survived and narration event 'kill_immune' created."
        print(outcome_msg); logger.info(outcome_msg)

    def test_handle_heal_success(self):
        msg = f"[START] {self._testMethodName} - Testing heal processing"
        print(f"\n{msg}"); logger.info(msg)
        
        night_outcomes = {202: {'status': None}, 101: {'status': None}}
        
        action_msg = "[ACTION] Executing handle_heal (202 -> 101)"
        print(action_msg); logger.info(action_msg)
        
        handle_heal(self.mock_game, 202, 101, night_outcomes)
        
        self.assertEqual(night_outcomes[101]['status'], 'healed')
        self.mock_game.narration_manager.add_event.assert_called_with('heal', doctor=self.player2, target=self.player1)
        
        outcome_msg = "[OUTCOME] Success! Status set to 'healed' and narration event 'heal' created."
        print(outcome_msg); logger.info(outcome_msg)

    def test_handle_block_success(self):
        msg = f"[START] {self._testMethodName} - Testing roleblock processing"
        print(f"\n{msg}"); logger.info(msg)
        
        night_outcomes = {202: {'status': None}, 101: {'status': None}}
        
        action_msg = "[ACTION] Executing handle_block (202 -> 101)"
        print(action_msg); logger.info(action_msg)
        
        handle_block(self.mock_game, 202, 101, night_outcomes)
        
        self.assertEqual(night_outcomes[101]['status'], 'blocked')
        self.mock_game.narration_manager.add_event.assert_called_with('block', blocker=self.player2, target=self.player1)
        
        outcome_msg = "[OUTCOME] Success! Target blocked and narration event 'block' created."
        print(outcome_msg); logger.info(outcome_msg)