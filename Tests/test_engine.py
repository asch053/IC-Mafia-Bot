import unittest
import asyncio
# <-- MODIFIED: Ensure patch is imported
from unittest.mock import MagicMock, AsyncMock, patch, call, ANY
from datetime import datetime, timezone, timedelta
 
 # It's good practice to set up the path if running tests from the root directory
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
 
from game.engine import Game
from game.player import Player
# Ensure get_role_instance is imported for use within the patched context
from game.roles import get_role_instance
 
 # Mock config
 # Ensure all potentially accessed config values are mocked
 # <-- MODIFIED: Assign the mock to a variable named 'config'
config = MagicMock(
    MAX_MISSED_VOTES=2,
    signup_loop_interval_seconds=15,
    min_players=6,
    ANNOUNCEMENT_CHANNEL_ID=1,
    SIGN_UP_HERE_CHANNEL_ID=2,
    RULES_AND_ROLES_CHANNEL_ID=3,
    STORIES_CHANNEL_ID=4,
    VOTING_CHANNEL_ID=5,
    TALKY_TALKY_CHANNEL_ID=6,
    MOD_CHANNEL_ID=7,
    LIVING_PLAYER_ROLE_ID=10,
    DEAD_PLAYER_ROLE_ID=11,
    SPECTATOR_ROLE_ID=12,
    MOD_ROLE_ID=13
)
# Assign the mock back to sys.modules if needed by other imports, though direct use is safer
sys.modules['config'] = config


# Helper to run async tests
def async_test(f):
    def wrapper(*args, **kwargs):
        # Use asyncio.run() which handles loop creation/cleanup
        return asyncio.run(f(*args, **kwargs))
    return wrapper

# <-- Patch applied as a class decorator
@patch('game.roles.load_data') 
class TestGameEngine(unittest.TestCase):

    # <-- MODIFIED: REMOVED mock_load_data argument from setUp
    def setUp(self, mock_load_data): 
        """Set up a fresh Game instance and mocks for each test."""
        # Configure the mock passed by the decorator
        mock_load_data.side_effect = self.mock_load_data_side_effect
        
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        self.mock_cleanup = MagicMock()
        self.mock_channel = AsyncMock()

        # Mock the narration manager
        self.mock_narration_manager = MagicMock()

        # Initialize the game *after* patch is active via decorator
        self.game = Game(self.mock_bot, self.mock_guild, self.mock_cleanup)

        # Manually replace the game's manager with our mock
        self.game.narration_manager = self.mock_narration_manager

        # Pre-populate discord_roles for tests needing role updates
        # <-- MODIFIED: Use the mocked config object
        self.game.discord_roles = {
            "living": MagicMock(id=config.LIVING_PLAYER_ROLE_ID), 
            "dead": MagicMock(id=config.DEAD_PLAYER_ROLE_ID),
            "spectator": MagicMock(id=config.SPECTATOR_ROLE_ID),
            "mod": MagicMock(id=config.MOD_ROLE_ID)
        }

    # Define the side effect method used by the patch
    def mock_load_data_side_effect(self, filepath, error_default=None):
        """Simulate loading data from files."""
        base_filename = os.path.basename(filepath)
        if "role_definition.json" in base_filename:
            return {
                "Townie": {"base": "Town", "description": "D", "short_description": "SD"},
                "Godfather": {"base": "Mafia", "description": "D", "short_description": "SD", "abilities": {"kill": 1}, "is_night_immune": True, "night_priority": 3},
                "Role Blocker": {"base": "Town", "description": "D", "short_description": "SD", "abilities": {"block": 1}, "night_priority": 1},
                "Doctor": {"base": "Town", "description": "D", "short_description": "SD", "abilities": {"heal": 1}, "night_priority": 2},
                "Jester": {"base": "NeutralEvil", "description": "D", "short_description": "SD", "abilities": {}, "win_condition": "jester_lynch"},
            }
        if "game_modes.json" in base_filename:
            return {"classic": {"min_players": 6, "roles": ["Townie", "Godfather"]}}
        if "discord_roles.json" in base_filename:
            # <-- MODIFIED: Use the mocked config object
            return {
                "living": {"id": config.LIVING_PLAYER_ROLE_ID, "name": "Living"},
                "dead": {"id": config.DEAD_PLAYER_ROLE_ID, "name": "Dead"},
                "spectator": {"id": config.SPECTATOR_ROLE_ID, "name": "Spectator"},
                "mod": {"id": config.MOD_ROLE_ID, "name": "Mod"}
            }
        return error_default if error_default is not None else {}

    def _add_test_players(self, count):
        """Helper to add a number of mock players to the game."""
        for i in range(1, count + 1):
            self.game.players[i] = Player(user_id=i, discord_name=f"TestUser{i}", display_name=f"TestUser{i}")
            self.game.players[i].kill = MagicMock() 

    @async_test
    async def test_add_player_success(self):
        self.game.game_settings["current_phase"] = "signup"
        mock_user = MagicMock(name="TestUser101", display_name="TestUser101")
        mock_user.id = 101 
        mock_interaction = AsyncMock()
        with patch('game.engine.update_player_discord_roles', new_callable=AsyncMock) as mock_update_roles:
            response = await self.game.add_player(mock_interaction, mock_user, self.mock_channel)
            self.assertIn(101, self.game.players)
            self.assertEqual(self.game.players[101].display_name, "TestUser101")
            self.assertFalse(self.game.players[101].is_npc) 
            self.assertIn("You have successfully signed up", response)
            mock_update_roles.assert_called_once()

    # --- Tests for record_night_action (Validation) ---

    @async_test
    async def test_record_night_action_fail_not_night(self):
        self._add_test_players(2)
        self.game.game_settings["current_phase"] = "day" 
        mock_interaction = AsyncMock(user=MagicMock(id=1)) 
        response = await self.game.record_night_action(mock_interaction, "2", 'kill') 
        self.assertIn("You can only perform actions during the night.", response)
        self.assertEqual(len(self.game.night_actions), 0)

    @async_test
    async def test_record_night_action_fail_dead_player(self):
        self._add_test_players(2)
        self.game.players[1].is_alive = False 
        self.game.game_settings["current_phase"] = "night"
        mock_interaction = AsyncMock(user=MagicMock(id=1))
        response = await self.game.record_night_action(mock_interaction, "2", 'kill')
        self.assertIn("You are not able to perform actions in the game.", response)
        self.assertEqual(len(self.game.night_actions), 0)

    @async_test
    async def test_record_night_action_fail_no_ability(self):
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Townie")) 
        self.assertIsNotNone(self.game.players[1].role) 
        self.game.game_settings["current_phase"] = "night"
        mock_interaction = AsyncMock(user=MagicMock(id=1))
        response = await self.game.record_night_action(mock_interaction, "2", 'kill')
        self.assertIn("Your role does not have the 'kill' ability", response)
        self.assertEqual(len(self.game.night_actions), 0)

    @async_test
    async def test_record_night_action_fail_target_dead(self):
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Godfather")) 
        self.assertIsNotNone(self.game.players[1].role) 
        self.game.players[2].is_alive = False 
        self.game.game_settings["current_phase"] = "night"
        mock_interaction = AsyncMock(user=MagicMock(id=1))
        response = await self.game.record_night_action(mock_interaction, "2", 'kill') 
        self.assertIn("You cannot target a dead player", response) 
        self.assertEqual(len(self.game.night_actions), 0)

    @async_test
    async def test_record_night_action_fail_target_self_kill(self):
        self._add_test_players(1)
        self.game.players[1].assign_role(get_role_instance("Godfather")) 
        self.assertIsNotNone(self.game.players[1].role) 
        self.game.game_settings["current_phase"] = "night"
        mock_interaction = AsyncMock(user=MagicMock(id=1))
        response = await self.game.record_night_action(mock_interaction, "1", 'kill')
        self.assertIn("You cannot target yourself with this ability", response) 
        self.assertEqual(len(self.game.night_actions), 0)

    @async_test
    async def test_record_night_action_fail_target_same_heal(self):
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Doctor")) 
        self.assertIsNotNone(self.game.players[1].role) 
        self.game.players[1].last_action_target_id = 2 
        self.game.game_settings["current_phase"] = "night"
        mock_interaction = AsyncMock(user=MagicMock(id=1))
        response = await self.game.record_night_action(mock_interaction, "2", 'heal')
        self.assertIn("You cannot heal the same person two nights in a row", response)
        self.assertEqual(len(self.game.night_actions), 0)

    @async_test
    async def test_record_night_action_success(self):
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Godfather")) 
        self.assertIsNotNone(self.game.players[1].role) 
        self.game.game_settings["current_phase"] = "night"
        mock_interaction = AsyncMock(user=MagicMock(id=1))
        response = await self.game.record_night_action(mock_interaction, "2", 'kill')
        self.assertIn("Your action (kill on TestUser2) has been recorded.", response) 
        self.assertEqual(len(self.game.night_actions), 1)
        self.assertEqual(self.game.night_actions[1]['action'], 'kill')
        self.assertEqual(self.game.night_actions[1]['target_id'], 2)

    # --- Tests for process_night_actions (Priority) ---

    @patch('game.engine.actions.handle_kill')
    @patch('game.engine.actions.handle_block')
    @async_test
    async def test_process_night_actions_priority_block_vs_kill(
        self, mock_handle_block: MagicMock, mock_handle_kill: MagicMock
    ):
        self._add_test_players(3)
        self.game.players[1].assign_role(get_role_instance("Role Blocker")) 
        self.game.players[2].assign_role(get_role_instance("Godfather"))    
        self.game.players[3].assign_role(get_role_instance("Townie"))
        self.assertIsNotNone(self.game.players[1].role) 
        self.assertIsNotNone(self.game.players[2].role)
        self.assertIsNotNone(self.game.players[3].role)
        self.game.night_actions = {
            2: {'action': 'kill', 'target_id': 3, 'priority': 3, 'actor': self.game.players[2]},
            1: {'action': 'block', 'target_id': 2, 'priority': 1, 'actor': self.game.players[1]},
        }
        manager = MagicMock()
        manager.attach_mock(mock_handle_block, 'handle_block')
        manager.attach_mock(mock_handle_kill, 'handle_kill')
        await self.game.process_night_actions()
        expected_calls = [ call.handle_block(self.game, 1, 2, ANY), call.handle_kill(self.game, 2, 3, ANY) ]
        self.assertEqual(manager.mock_calls, expected_calls)

    # --- Tests for _resolve_night_deaths (Resolution) ---

    @async_test
    async def test_resolve_night_deaths_successful_save(self):
        self._add_test_players(3)
        self.game.players[1].assign_role(get_role_instance("Godfather")) 
        self.game.players[2].assign_role(get_role_instance("Townie"))    
        self.game.players[3].assign_role(get_role_instance("Doctor"))    
        self.assertIsNotNone(self.game.players[1].role) 
        self.assertIsNotNone(self.game.players[2].role)
        self.assertIsNotNone(self.game.players[3].role)
        self.game.kill_attempts_on[2] = [1] 
        self.game.heals_on_players[2] = [3]
        await self.game._resolve_night_deaths()
        self.game.players[2].kill.assert_not_called()
        self.mock_narration_manager.add_event.assert_called_with( 'save', healer=self.game.players[3], victim=self.game.players[2], killer=self.game.players[1] )

    @async_test
    async def test_resolve_night_deaths_unsaved_kill(self):
        self._add_test_players(3) 
        self.game.players[1].assign_role(get_role_instance("Godfather"))
        self.game.players[2].assign_role(get_role_instance("Townie")) 
        self.assertIsNotNone(self.game.players[1].role) 
        self.assertIsNotNone(self.game.players[2].role)
        self.game.kill_attempts_on[2] = [1]
        self.game.heals_on_players = {} 
        await self.game._resolve_night_deaths()
        self.game.players[2].kill.assert_called_with("Night 0", "Killed by Godfather") 
        self.mock_narration_manager.add_event.assert_called_with( 'kill', killer=self.game.players[1], victim=self.game.players[2] )

    # --- Tests for tally_votes (Outcomes) ---

    @async_test
    async def test_tally_votes_no_lynch(self):
        self._add_test_players(3)
        self.game.lynch_votes = {}
        await self.game.tally_votes()
        self.mock_narration_manager.add_event.assert_called_with('no_lynch')

    @async_test
    async def test_tally_votes_tie_lynch(self):
        self._add_test_players(4)
        self.game.players[1].assign_role(get_role_instance("Townie"))
        self.game.players[2].assign_role(get_role_instance("Townie"))
        self.game.players[3].assign_role(get_role_instance("Townie"))
        self.game.players[4].assign_role(get_role_instance("Townie"))
        self.assertIsNotNone(self.game.players[1].role) 
        self.assertIsNotNone(self.game.players[2].role)
        self.assertIsNotNone(self.game.players[3].role)
        self.assertIsNotNone(self.game.players[4].role)
        self.game.lynch_votes = { 1: [3, 4], 2: [1, 2] }
        await self.game.tally_votes()
        self.game.players[1].kill.assert_called_with("Day 0", "Lynched by the town")
        self.game.players[2].kill.assert_called_with("Day 0", "Lynched by the town")
        self.mock_narration_manager.add_event.assert_called_with( 'lynch', victims=[self.game.players[1], self.game.players[2]], details=ANY )

    @async_test
    async def test_tally_votes_inactivity_kill(self):
        self._add_test_players(3)
        self.game.players[1].assign_role(get_role_instance("Townie"))
        self.game.players[2].assign_role(get_role_instance("Townie"))
        self.game.players[3].assign_role(get_role_instance("Townie"))
        self.assertIsNotNone(self.game.players[1].role) 
        self.assertIsNotNone(self.game.players[2].role)
        self.assertIsNotNone(self.game.players[3].role)
        self.game.players[1].missed_votes = 1
        self.game.lynch_votes = {2: [3]} 
        await self.game.tally_votes()
        self.game.players[1].kill.assert_called_with("Day 0", "Inactivity")
        self.mock_narration_manager.add_event.assert_any_call( 'inactivity_kill', victims=[self.game.players[1]] )
        self.game.players[2].kill.assert_called_with("Day 0", "Lynched by the town")
        self.mock_narration_manager.add_event.assert_any_call( 'lynch', victims=[self.game.players[2]], details=ANY )
        self.game.players[3].kill.assert_not_called()

    # --- Win Condition Tests ---
    
    @async_test
    async def test_tally_votes_jester_win(self):
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Jester"))
        self.game.players[2].assign_role(get_role_instance("Townie"))
        self.assertIsNotNone(self.game.players[1].role) 
        self.assertIsNotNone(self.game.players[2].role)
        self.game.lynch_votes = {1: [2]}
        winner = await self.game.tally_votes() 
        self.game.players[1].kill.assert_called_with("Day 0", "Lynched by the town")
        self.mock_narration_manager.add_event.assert_any_call( 'jester_win', victim=self.game.players[1] )
        self.assertEqual(winner, "Jester") 

    def test_check_win_conditions_town_win(self):
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Townie"))
        self.game.players[2].assign_role(get_role_instance("Godfather"))
        self.assertIsNotNone(self.game.players[1].role) 
        self.assertIsNotNone(self.game.players[2].role)
        self.game.players[2].is_alive = False
        winner = self.game.check_win_conditions()
        self.assertEqual(winner, "Town")

    def test_check_win_conditions_mafia_win(self):
        self.game.game_settings["current_phase"] = "day"
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Townie"))
        self.game.players[2].assign_role(get_role_instance("Godfather"))
        self.assertIsNotNone(self.game.players[1].role) 
        self.assertIsNotNone(self.game.players[2].role)
        winner = self.game.check_win_conditions()
        self.assertEqual(winner, "Mafia")

    def test_check_win_conditions_draw(self):
        self._add_test_players(2)
        self.game.players[1].is_alive = False
        self.game.players[2].is_alive = False
        winner = self.game.check_win_conditions()
        self.assertEqual(winner, "Draw")

if __name__ == '__main__':
    unittest.main()
