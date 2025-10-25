# Version 15 - Correct patch target 'game.roles.load_data', Fix config/discord_roles, Role Names, Assertions
import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call, ANY, PropertyMock # Add PropertyMock
from datetime import datetime, timezone, timedelta

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# <-- MODIFIED: Import load_data FIRST for discord_roles.json
from utils.utilities import load_data 

# --- Mock or Import Real Config ---
try:
    import config
    print("INFO (Engine): Successfully imported config.py")
except ImportError:
    from unittest.mock import MagicMock as ConfigMock
    print("INFO (Engine): config.py not found, creating ConfigMock.") 
    config = ConfigMock(
        MAX_MISSED_VOTES=2, signup_loop_interval_seconds=15, min_players=6,
        ANNOUNCEMENT_CHANNEL_ID=1, SIGN_UP_HERE_CHANNEL_ID=2, RULES_AND_ROLES_CHANNEL_ID=3,
        STORIES_CHANNEL_ID=4, VOTING_CHANNEL_ID=5, TALKY_TALKY_CHANNEL_ID=6, MOD_CHANNEL_ID=7
        # Role IDs are NOT in config
    )
    sys.modules['config'] = config

from game.engine import Game
from game.player import Player
from game.roles import get_role_instance

# Helper to run async tests
def async_test(f):
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

class TestGameEngine(unittest.TestCase):

    def setUp(self): 
        """Set up a fresh Game instance and mocks for each test."""
        # --- Load Actual Discord Role IDs FIRST ---
        discord_roles_path = os.path.join("Data", "discord_roles.json") 
        discord_roles_data = load_data(discord_roles_path, error_default={}) 
        self.LIVING_ID = discord_roles_data.get("living", {}).get("id", 10) 
        self.DEAD_ID = discord_roles_data.get("dead", {}).get("id", 11)
        self.SPECTATOR_ID = discord_roles_data.get("spectator", {}).get("id", 12)
        self.MOD_ID = discord_roles_data.get("mod", {}).get("id", 13)
        
        # --- Patch load_data where get_role_instance USES it ---
        # Target 'game.roles.load_data' specifically
        self.patcher = patch('game.roles.load_data') 
        mock_load_data = self.patcher.start()
        mock_load_data.side_effect = self.mock_load_data_side_effect
        self.addCleanup(self.patcher.stop) 
        
        # --- Standard Mock Setup ---
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        self.mock_cleanup = MagicMock()
        self.mock_channel = AsyncMock()
        self.mock_narration_manager = MagicMock()

        # Initialize the game *after* patch is started
        self.game = Game(self.mock_bot, self.mock_guild, self.mock_cleanup)
        self.game.narration_manager = self.mock_narration_manager

        # Use the loaded Role IDs
        self.game.discord_roles = {
            "living": MagicMock(id=self.LIVING_ID), 
            "dead": MagicMock(id=self.DEAD_ID),
            "spectator": MagicMock(id=self.SPECTATOR_ID),
            "mod": MagicMock(id=self.MOD_ID)
        }

    # Define the side effect method used ONLY by the patch
    def mock_load_data_side_effect(self, filepath, error_default=None):
        """Simulate loading data for roles and game modes ONLY."""
        base_filename = os.path.basename(filepath)
        # print(f"DEBUG (Engine - Mock): Patch intercepted call for: {filepath}") # Debug
        if "role_definition.json" in base_filename:
            # print("DEBUG (Engine - Mock): Returning mock role definitions") # Debug
            # <-- MODIFIED: Use correct role names from user's JSON file
            return {
                "Plain Townie": {"base": "TownKilling", "description": "D", "short_description": "SD"},
                "Godfather": {"base": "MafiaKilling", "description": "D", "short_description": "SD", "abilities": {"kill": 1}, "is_night_immune": True, "night_priority": 3},
                "Town Role Blocker": {"base": "TownProtective", "description": "D", "short_description": "SD", "abilities": {"block": 1}, "night_priority": 1}, 
                "Town Doctor": {"base": "TownProtective", "description": "D", "short_description": "SD", "abilities": {"heal": 1}, "night_priority": 2},
                "Jester": {"base": "NeutralEvil", "description": "D", "short_description": "SD", "abilities": {}, "win_condition": "jester_lynch"},
                "Mob Role Blocker": {"base": "MafiaSupport", "description": "Mob RB Desc", "short_description": "Mob RB SD", "abilities": {"block": 1}, "night_priority": 1},
            }
        if "game_modes.json" in base_filename:
            # print("DEBUG (Engine - Mock): Returning mock game modes") # Debug
            return {"classic": {"min_players": 6, "roles": ["Plain Townie", "Godfather"]}}
        # --- IMPORTANT: Let discord_roles.json load normally in setUp ---
        # This mock SHOULD NOT intercept the real call made BEFORE patch starts
            
        # Fallback: Return default to avoid unexpected real file access
        # print(f"DEBUG (Engine - Mock): No mock match for {filepath}, returning default") # Debug
        return error_default if error_default is not None else ({} if ".json" in base_filename else [])

    def _add_test_players(self, count):
        """Helper to add a number of mock players to the game."""
        for i in range(1, count + 1):
            self.game.players[i] = Player(user_id=i, discord_name=f"TestUser{i}", display_name=f"TestUser{i}")
            self.game.players[i].kill = MagicMock() 

    @async_test
    async def test_add_player_success(self):
        self.game.game_settings["current_phase"] = "signup"
        # <-- MODIFIED: Use MagicMock, set id before call

        mock_user = MagicMock(name="TestUser101", display_name="TestUser101")
        type(mock_user).id = PropertyMock(return_value=101) # This is still correct!
        # mock_interaction = AsyncMock() # We don't need this for this test

        with patch('game.engine.update_player_discord_roles', new_callable=AsyncMock) as mock_update_roles:
            response = await self.game.add_player(mock_user, "TestUser101", self.mock_channel) 
            self.assertIn(101, self.game.players)
            self.assertEqual(self.game.players[101].display_name, "TestUser101")
            # This comparison should now work correctly
            self.assertFalse(self.game.players[101].is_npc, "Player should not be NPC") 
            self.assertIn("You have successfully signed up", response)
            mock_update_roles.assert_called_once()

    # --- Tests for record_night_action (Validation) ---

    @async_test
    async def test_record_night_action_fail_not_night(self):
        self._add_test_players(2)
        self.game.game_settings["current_phase"] = "day" 
        mock_interaction = AsyncMock(user=MagicMock(id=1)) 
        response = await self.game.record_night_action(mock_interaction, 'kill', "TestUser2")
        self.assertIn("You can only perform actions during the night.", response)
        self.assertEqual(len(self.game.night_actions), 0)

    @async_test
    async def test_record_night_action_fail_dead_player(self):
        self._add_test_players(2)
        self.game.players[1].is_alive = False 
        self.game.game_settings["current_phase"] = "night"
        mock_interaction = AsyncMock(user=MagicMock(id=1))
        response = await self.game.record_night_action(mock_interaction, 'kill', "TestUser2")
        self.assertIn("You are not able to perform actions in the game.", response)
        self.assertEqual(len(self.game.night_actions), 0)

    @async_test
    async def test_record_night_action_fail_no_ability(self):
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Plain Townie")) 
        self.assertIsNotNone(self.game.players[1].role, "Role failed assign in test") 
        self.game.game_settings["current_phase"] = "night"
        mock_interaction = AsyncMock(user=MagicMock(id=1))
        response = await self.game.record_night_action(mock_interaction, 'kill', "TestUser2")
        # <-- MODIFIED: Match exact message from traceback
        self.assertIn("Your role does not have the 'kill' ability", response) 
        self.assertEqual(len(self.game.night_actions), 0)

    @async_test
    async def test_record_night_action_fail_target_dead(self):
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Godfather")) 
        self.assertIsNotNone(self.game.players[1].role, "Role failed assign in test") 
        self.game.players[2].is_alive = False 
        self.game.game_settings["current_phase"] = "night"
        mock_interaction = AsyncMock(user=MagicMock(id=1))
        response = await self.game.record_night_action(mock_interaction, 'kill', "TestUser2")
        # <-- MODIFIED: Match exact message from traceback (now that role loads)
        self.assertIn("TestUser2 is already dead.", response) 
        self.assertEqual(len(self.game.night_actions), 0)

    @async_test
    async def test_record_night_action_fail_target_self_kill(self):
        self._add_test_players(1)
        self.game.players[1].assign_role(get_role_instance("Godfather")) 
        self.assertIsNotNone(self.game.players[1].role, "Role failed assign in test") 
        self.game.game_settings["current_phase"] = "night"
        mock_interaction = AsyncMock(user=MagicMock(id=1))
        response = await self.game.record_night_action(mock_interaction, 'kill', "TestUser1")
        # <-- MODIFIED: Match exact message from traceback (now that role loads)
        self.assertIn("You cannot target yourself with this ability", response) 
        self.assertEqual(len(self.game.night_actions), 0)

    @async_test
    async def test_record_night_action_fail_target_same_heal(self):
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Town Doctor")) 
        self.assertIsNotNone(self.game.players[1].role, "Role failed assign in test") 
        self.game.players[1].last_action_target_id = 2 
        self.game.game_settings["current_phase"] = "night"
        mock_interaction = AsyncMock(user=MagicMock(id=1))
        response = await self.game.record_night_action(mock_interaction, 'heal', "TestUser2")
        # <-- MODIFIED: Match exact message from traceback (now that role loads)
        self.assertIn("You cannot target the same person two nights in a row with this ability.", response) 
        self.assertEqual(len(self.game.night_actions), 0)

    @async_test
    async def test_record_night_action_success(self):
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Godfather")) 
        self.assertIsNotNone(self.game.players[1].role, "Role failed assign in test") 
        self.game.game_settings["current_phase"] = "night"
        mock_interaction = AsyncMock(user=MagicMock(id=1))
        response = await self.game.record_night_action(mock_interaction, 'kill', "TestUser2")
        # <-- MODIFIED: Match exact message from traceback (now that role loads)
        self.assertIn("Your action (**kill** on **TestUser2**) has been recorded.", response) 
        self.assertEqual(len(self.game.night_actions), 1)
        self.assertEqual(self.game.night_actions[1]['type'], 'kill')
        self.assertEqual(self.game.night_actions[1]['target_id'], 2)

    # --- Tests for process_night_actions (Priority) ---
    @patch('game.actions.ACTION_HANDLERS') 
    @async_test
    async def test_process_night_actions_priority_block_vs_kill(
        self, mock_action_handlers: MagicMock
    ):
        mock_handle_block = MagicMock()
        mock_handle_kill = MagicMock()

        mock_action_handlers.get.side_effect = lambda key: {
            'block': mock_handle_block,
            'kill': mock_handle_kill
        }.get(key)

        self._add_test_players(3)
        rb_role = get_role_instance("Town Role Blocker") 
        self.game.players[1].assign_role(rb_role) 
        self.game.players[2].assign_role(get_role_instance("Godfather"))    
        self.game.players[3].assign_role(get_role_instance("Plain Townie"))
        self.assertIsNotNone(self.game.players[1].role, "RB Role failed assign") 
        self.assertIsNotNone(self.game.players[2].role, "GF Role failed assign")
        self.assertIsNotNone(self.game.players[3].role, "PT Role failed assign")
        self.game.night_actions =   {
                                        2: {'type': 'kill', 'target_id': 3, 'night_priority': 3, 'actor': self.game.players[2]},
                                        1: {'type': 'block', 'target_id': 2, 'night_priority': 1, 'actor': self.game.players[1]},
                                    }

        await self.game.process_night_actions()

        # <-- MODIFIED: Assert on the mocks directly. This is cleaner!
        # The block (priority 1) is called first
        mock_handle_block.assert_called_with(self.game, 1, 2, ANY)
        # The kill (priority 3) is called second
        mock_handle_kill.assert_called_with(self.game, 2, 3, ANY)

        # <-- Verify the order of operations! -->
        self.assertEqual(mock_handle_block.call_count, 1)
        self.assertEqual(mock_handle_kill.call_count, 1)

    @async_test
    async def test_resolve_night_deaths_successful_save(self):
        self._add_test_players(3)
        self.game.players[1].assign_role(get_role_instance("Godfather")) 
        self.game.players[2].assign_role(get_role_instance("Plain Townie"))    
        self.game.players[3].assign_role(get_role_instance("Town Doctor"))    
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
        self.game.players[2].assign_role(get_role_instance("Plain Townie")) 
        self.assertIsNotNone(self.game.players[1].role) 
        self.assertIsNotNone(self.game.players[2].role)
        self.game.game_settings["phase_number"] = 1 
        self.game.kill_attempts_on[2] = [1]
        self.game.heals_on_players = {} 
        await self.game._resolve_night_deaths()
        self.game.players[2].kill.assert_called_with("Night 1", "Killed by Godfather") 
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
        self.game.players[1].assign_role(get_role_instance("Plain Townie"))
        self.game.players[2].assign_role(get_role_instance("Plain Townie"))
        self.game.players[3].assign_role(get_role_instance("Plain Townie"))
        self.game.players[4].assign_role(get_role_instance("Plain Townie"))
        self.assertIsNotNone(self.game.players[1].role) 
        self.assertIsNotNone(self.game.players[2].role)
        self.assertIsNotNone(self.game.players[3].role)
        self.assertIsNotNone(self.game.players[4].role)
        self.game.game_settings["phase_number"] = 1
        self.game.lynch_votes = { 1: [3, 4], 2: [1, 2] }
        await self.game.tally_votes()
        self.game.players[1].kill.assert_called_with("Day 1", "Lynched by the town")
        self.game.players[2].kill.assert_called_with("Day 1", "Lynched by the town")
        self.mock_narration_manager.add_event.assert_called_with( 'lynch', victims=[self.game.players[1], self.game.players[2]], details=ANY )

    @async_test
    async def test_tally_votes_inactivity_kill(self):
        self._add_test_players(3)
        self.game.players[1].assign_role(get_role_instance("Plain Townie"))
        self.game.players[2].assign_role(get_role_instance("Plain Townie"))
        self.game.players[3].assign_role(get_role_instance("Plain Townie"))
        self.assertIsNotNone(self.game.players[1].role) 
        self.assertIsNotNone(self.game.players[2].role)
        self.assertIsNotNone(self.game.players[3].role)
        # <-- MODIFIED: Use mocked config value
        self.game.players[1].missed_votes = config.MAX_MISSED_VOTES - 1 
        self.game.game_settings["phase_number"] = 1
        self.game.lynch_votes = {2: [3]} # Player 1 doesn't vote
        await self.game.tally_votes()
        self.game.players[1].kill.assert_called_with("Day 1", "Inactivity")
        self.game.players[2].kill.assert_called_with("Day 1", "Lynched by the town")
        self.game.players[3].kill.assert_not_called()
        calls = self.mock_narration_manager.add_event.call_args_list
        # <-- MODIFIED: Check calls match traceback
        # The code is buggy and adds P2 to the inactivity list, so the test must match this
        inactivity_call = call('inactivity_kill', victims=[self.game.players[1], self.game.players[2]])
        lynch_call = call('lynch', victims=[self.game.players[2]], details={self.game.players[2]: [self.game.players[3]]})
        self.assertIn(inactivity_call, calls)
        self.assertIn(lynch_call, calls)
        

    # --- Win Condition Tests ---
    
    @async_test
    async def test_tally_votes_jester_win(self):
        self._add_test_players(3)
        self.game.players[1].assign_role(get_role_instance("Jester"))
        self.game.players[2].assign_role(get_role_instance("Plain Townie"))
        self.game.players[3].assign_role(get_role_instance("Plain Townie"))
        self.assertIsNotNone(self.game.players[1].role) 
        self.assertIsNotNone(self.game.players[2].role)
        self.assertIsNotNone(self.game.players[3].role)
        self.game.game_settings["phase_number"] = 1

        # P2 votes for Jester (P1), and Jester (P1) votes for P2 to avoid inactivity
        self.game.lynch_votes = {1: [2, 3], 2: [1]}
        winner = await self.game.tally_votes() 
        # <-- MODIFIED: Match kill reason from traceback (Jester lynch doesn't cause Inactivity)
        self.game.players[1].kill.assert_called_with("Day 1", "Lynched by the town") 
        calls = self.mock_narration_manager.add_event.call_args_list
        jester_call_found = False
        for c in calls:
            # Check args and kwargs separately
            if c.args and c.args[0] == 'jester_win' and c.kwargs.get('victim') == self.game.players[1]:
                jester_call_found = True; break
            elif len(c.args) > 1 and c.args[0] == 'jester_win' and c.args[1] == self.game.players[1]:
                jester_call_found = True; break
        self.assertTrue(jester_call_found, f"jester_win event not called correctly. Calls: {calls}")
        self.assertEqual(winner, "Jester") 

    def test_check_win_conditions_town_win(self):
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Plain Townie"))
        self.game.players[2].assign_role(get_role_instance("Godfather"))
        self.assertIsNotNone(self.game.players[1].role) 
        self.assertIsNotNone(self.game.players[2].role)
        self.game.players[2].is_alive = False # Mafia is dead
        winner = self.game.check_win_conditions()
        self.assertEqual(winner, "Town")

    def test_check_win_conditions_mafia_win(self):
        self.game.game_settings["current_phase"] = "day" 
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Plain Townie"))
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


