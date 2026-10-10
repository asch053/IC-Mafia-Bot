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

    async def test_npc_night_actions_auto_queue(self):
        msg = f"[START] {self._testMethodName} - Testing NPC automated night actions"
        print(f"\n{msg}"); logger.info(msg)

        self.game.game_settings["current_phase"] = "night"
        self._add_test_players(2)
        # Player 1 is Town, Player 2 is NPC Godfather
        self.game.players[1].assign_role(GameRole(name="Plain Townie", alignment="Town", description="Town", short_description="Town"))
        
        npc_gf = Player(-1, "BotGodfather", "BotGodfather")
        npc_gf.assign_role(GameRole(name="Godfather", alignment="Mafia", description="GF", short_description="GF", abilities={"kill": "Kill"}))
        self.game.players[-1] = npc_gf

        await self.game.process_npc_night_actions()

        self.assertIn(-1, self.game.night_actions)
        self.assertEqual(self.game.night_actions[-1]["type"], "kill")
        self.assertIn(self.game.night_actions[-1]["target_id"], [1, 2])
        print(f"[OUTCOME] Success! NPC Godfather targeted Player {self.game.night_actions[-1]['target_id']} with kill action.")

    async def test_npc_day_voting_auto_vote(self):
        msg = f"[START] {self._testMethodName} - Testing NPC automated day voting"
        print(f"\n{msg}"); logger.info(msg)

        self.game.game_settings["current_phase"] = "day"
        self.game.game_settings["phase_number"] = 1
        self._add_test_players(2)

        npc = Player(-2, "BotTownie", "BotTownie")
        npc.assign_role(GameRole(name="Plain Townie", alignment="Town", description="Town", short_description="Town"))
        self.game.players[-2] = npc

        await self.game.process_npc_votes()

        self.assertIsNotNone(npc.action_target)
        self.assertIn(npc.action_target, [1, 2])
        self.assertIn(-2, self.game.lynch_votes[npc.action_target])
        print(f"[OUTCOME] Success! NPC voted for target ID {npc.action_target}.")

    def test_status_message_draw_game_over(self):
        """Verifies status message displays Draw outcome cleanly without Living Players: (0)."""
        self._add_test_players(2)
        # Both players eliminated
        for p in self.game.players.values():
            p.kill("Night 1", "Night Kill")
        
        self.game.game_settings['is_epilogue'] = True
        self.game.game_settings['winner'] = "Draw"
        self.game.game_settings['current_phase'] = "conclusion"

        status_msg = self.game.get_status_message()
        self.assertIn("Game Outcome:** DRAW", status_msg)
        self.assertNotIn("Living Players:** (0)", status_msg)

    async def test_remove_player_boolean_returns(self):
        """Verifies remove_player returns True when removed, and False when player absent or outside signup."""
        self.game.game_settings['current_phase'] = 'signup'
        mock_user = AsyncMock()
        mock_user.id = 999
        mock_user.name = "Leaver"
        mock_user.display_name = "Leaver"

        with patch('game.engine.update_player_discord_roles', new_callable=AsyncMock):
            # Not in game yet
            self.assertFalse(await self.game.remove_player(mock_user, self.mock_channel))

            # Add player then remove
            await self.game.add_player(mock_user, "Leaver", self.mock_channel)
            self.assertIn(999, self.game.players)
            self.assertTrue(await self.game.remove_player(mock_user, self.mock_channel))
            self.assertNotIn(999, self.game.players)

            # Outside signup phase
            self.game.game_settings['current_phase'] = 'day'
            self.assertFalse(await self.game.remove_player(mock_user, self.mock_channel))

    async def test_jester_win_on_tie_lynch(self):
        """Verifies that if a Jester is lynched in a tie multi-lynch, Jester win is awarded."""
        self.game.game_settings["current_phase"] = "day"
        self.game.game_settings["phase_number"] = 1
        self._add_test_players(4)

        # Player 1 is Townie, Player 2 is Jester, Player 3 and 4 vote
        self.game.players[1].assign_role(game.roles.get_role_instance("Plain Townie"))
        self.game.players[2].assign_role(game.roles.get_role_instance("Jester"))

        # Create a tie: Player 1 has 1 vote, Player 2 has 1 vote
        self.game.lynch_votes = {
            1: [3],
            2: [4]
        }

        winner = await self.game.tally_votes()
        self.assertEqual(winner, "Jester")
        self.assertEqual(self.game.game_settings.get("winning_team"), "Jester")

    async def test_persistence_date_regex_and_db_update(self):
        """Verifies persistence.update_modular_database extracts dates via re without NameError."""
        from game.engine.persistence import update_modular_database
        
        game_data = {
            "game_id": "20261010-120000",
            "game_type": "classic",
            "number_of_players": 5,
            "player_counts": {"town": 3, "mafia": 2, "neutral": 0},
            "winning_players": ["Alice"],
            "total_days": 3,
            "start_date_utc": "2026-10-10T12:00:00+00:00"
        }
        final_summary = {
            "player_data": [],
            "lynch_vote_history": []
        }

        with patch('Website.build_unified_leaderboard.build_unified_stats', return_value={}):
            with patch('builtins.open', unittest.mock.mock_open(read_data="[]")):
                with patch('os.replace'):
                    with patch('os.makedirs'):
                        # This should execute cleanly without raising NameError on 're'
                        await update_modular_database(self.game, game_data, final_summary, "Town")