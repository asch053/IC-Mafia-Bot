import unittest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
import sys
import os
import datetime
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 1. MUST BE FIRST: Load logger & environment mocks
from tests.test_0_logging import setup_test_logging
logger = setup_test_logging()

from game.engine import Game
from game.player import Player
from game.roles import GameRole
import game.roles

def mock_get_role_instance(role_name):
    abilities = {'kill': 'Kill'} if role_name in ["Godfather", "Mob Goon"] else {}
    if role_name == "Town Doctor": abilities = {'heal': 'Heal'}
    if role_name == "Town Role Blocker": abilities = {'block': 'Block'}
    
    return GameRole(name=role_name, alignment="Town", description="Mock", 
                    short_description="Mock", abilities=abilities, is_night_immune=False)

class TestGameEngine(unittest.IsolatedAsyncioTestCase):
    logger.info(f"--- Starting Test Suite: {__name__} ---")
    def setUp(self):
        self.mock_config = MagicMock()
        self.mock_config.MAX_MISSED_VOTES = 2
        self.mock_config.min_players = 3 
        
        patcher = patch('game.engine.config', self.mock_config)
        self.mock_config_patch = patcher.start()
        self.addCleanup(patcher.stop)

        role_patcher = patch('game.roles.get_role_instance', side_effect=mock_get_role_instance)
        self.mock_role_factory = role_patcher.start()
        self.addCleanup(role_patcher.stop)

        self.mock_bot = MagicMock()
        self.mock_bot.wait_for = AsyncMock()
        self.mock_guild = MagicMock()
        
        self.game = Game(self.mock_bot, self.mock_guild)
        self.game.game_settings['phase_end_time'] = datetime.now(timezone.utc) + timedelta(minutes=60) 
        self.mock_channel = AsyncMock()
        self.mock_bot.get_channel.return_value = self.mock_channel
        self.game.narration_manager = MagicMock()

    def _add_test_players(self, count):
        for i in range(1, count + 1):
            user = AsyncMock()
            user.id = i
            user.name = f"User{i}"
            user.display_name = f"TestUser{i}"
            player = Player(user.id, user.name, user.display_name)
            self.game.players[i] = player

    async def test_add_player_success(self):
        msg = f"[START] {self._testMethodName} - Testing player signup"
        print(f"\n{msg}"); logger.info(msg)
        
        self.game.game_settings['current_phase'] = 'signup'
         # Set phase end time in the future
        mock_user = AsyncMock(name="TestUser101", display_name="TestUser101")
        type(mock_user).id = PropertyMock(return_value=101) 
        
        action_msg = "[ACTION] Calling add_player..."
        print(action_msg); logger.info(action_msg)
        
        with patch('game.engine.update_player_discord_roles', new_callable=AsyncMock):
            response = await self.game.add_player(mock_user, "TestUser101", self.mock_channel)
            
            self.assertIn(101, self.game.players)
            self.assertIn("successfully signed up", response)
            
            outcome_msg = "[OUTCOME] Success! Player added to internal dict and success message generated."
            print(outcome_msg); logger.info(outcome_msg)

    def test_check_win_conditions_town_win(self):
        msg = f"[START] {self._testMethodName} - Testing Town win calculation"
        print(f"\n{msg}"); logger.info(msg)
        
        self.game.game_settings["current_phase"] = "day" 
        self._add_test_players(2)
        self.game.players[1].assign_role(game.roles.get_role_instance("Plain Townie"))
        self.game.players[2].assign_role(game.roles.get_role_instance("Godfather"))
        
        action_msg = "[ACTION] Killing the only Mafia member..."
        print(action_msg); logger.info(action_msg)
        self.game.players[2].is_alive = False 
        
        winner = self.game.check_win_conditions()
        self.assertEqual(winner, "Town")
        
        outcome_msg = f"[OUTCOME] Success! Town recognized as winner. Winner={winner}"
        print(outcome_msg); logger.info(outcome_msg)