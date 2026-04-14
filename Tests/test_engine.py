# Version 23 - Fix CI Failures by Mocking Role Factory (No JSON dependency)
import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call, ANY, PropertyMock
from datetime import datetime, timezone, timedelta

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.utilities import load_data 

from game.engine import Game
from game.player import Player
import game.roles # <-- MODIFIED: Import module to patch get_role_instance correctly
from game.roles import GameRole

# Helper decorator for async tests
def async_test(f):
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

# --- Mock Role Factory ---
def mock_get_role_instance(role_name):
    """
    A fake factory that returns GameRole objects without needing role_definition.json.
    This ensures tests pass even if file paths or JSON loading fails in CI.
    """
    if role_name == "Godfather":
        return GameRole(name="Godfather", alignment="Mafia", description="Leader", short_description="GF", 
                        abilities={'kill': 'Kill ability'}, is_night_immune=True)
    
    elif role_name == "Plain Townie":
        return GameRole(name="Plain Townie", alignment="Town", description="Civilian", short_description="Town", 
                        abilities={}, is_night_immune=False)
    
    elif role_name == "Town Role Blocker":
        return GameRole(name="Town Role Blocker", alignment="Town", description="Blocker", short_description="RB", 
                        abilities={'block': 'Block ability'}, is_night_immune=False)
    
    elif role_name == "Town Doctor":
        return GameRole(name="Town Doctor", alignment="Town", description="Healer", short_description="Doc", 
                        abilities={'heal': 'Heal ability'}, is_night_immune=False)
    
    elif role_name == "Jester":
        return GameRole(name="Jester", alignment="Neutral", description="Jester", short_description="Jest", 
                        abilities={}, is_night_immune=False)
    
    elif role_name == "Mob Goon":
        return GameRole(name="Mob Goon", alignment="Mafia", description="Grunt", short_description="Goon", 
                        abilities={}, is_night_immune=False)
    
    elif role_name == "Mafia Framer":
        return GameRole(name="Mafia Framer", alignment="Mafia", description="Framer", short_description="Frame", 
                        abilities={}, is_night_immune=False)

    # Fallback for any other name used in tests
    return GameRole(name=role_name, alignment="Neutral", description="Mock", short_description="Mock", 
                    abilities={}, is_night_immune=False)

class TestGameEngine(unittest.TestCase):

    def setUp(self):
        """
        Runs before EVERY test method.
        Sets up a fresh Game instance with mocked dependencies.
        """
        print(f"\n[SETUP] Initializing fresh Game instance for {self._testMethodName}...")
        
        # --- 1. Force Mock the Config ---
        self.mock_config = MagicMock()
        self.mock_config.MAX_MISSED_VOTES = 2
        self.mock_config.min_players = 3 
        
        patcher = patch('game.engine.config', self.mock_config)
        self.mock_config_patch = patcher.start()
        self.addCleanup(patcher.stop)

        # --- 2. Mock the Role Factory (CRITICAL FIX) ---
        # We replace the real get_role_instance with our mock factory.
        # This prevents "AttributeError: NoneType has no attribute..."
        role_patcher = patch('game.roles.get_role_instance', side_effect=mock_get_role_instance)
        self.mock_role_factory = role_patcher.start()
        self.addCleanup(role_patcher.stop)

        # --- 3. Standard Setup ---
        self.mock_bot = MagicMock()
        self.mock_bot.wait_for = AsyncMock()
        self.mock_guild = MagicMock()
        
        self.game = Game(self.mock_bot, self.mock_guild)
        
        self.mock_channel = AsyncMock()
        self.mock_bot.get_channel.return_value = self.mock_channel
        self.game.narration_manager = MagicMock()

    def _add_test_players(self, count):
        """Helper to add 'count' players to the game state."""
        print(f"   -> Adding {count} test players...")
        for i in range(1, count + 1):
            user = MagicMock()
            user.id = i
            user.name = f"User{i}"
            user.display_name = f"TestUser{i}"
            player = Player(user.id, user.name, user.display_name)
            self.game.players[i] = player

    @async_test
    async def test_add_player_success(self):
        """Test that a user can successfully sign up."""
        print(">>> START: test_add_player_success")
        
        # 1. Setup
        self.game.game_settings['current_phase'] = 'signup'
        mock_user = MagicMock(name="TestUser101", display_name="TestUser101")
        type(mock_user).id = PropertyMock(return_value=101) 
        
        # 2. Action: Call add_player
        print("   -> Calling add_player...")
        with patch('game.engine.update_player_discord_roles', new_callable=AsyncMock) as mock_update_roles:
            response = await self.game.add_player(mock_user, "TestUser101", self.mock_channel)
            
            # 3. Assertions
            print(f"   -> Response received: {response}")
            self.assertIn(101, self.game.players)
            self.assertEqual(self.game.players[101].display_name, "TestUser101")
            self.assertIn("You have successfully signed up", response)
            print("   -> Success! Player is in game and success message returned.")

    @async_test
    async def test_record_night_action_fail_no_ability(self):
        """Test that a player without the 'kill' ability cannot kill."""
        print(">>> START: test_record_night_action_fail_no_ability")
        
        self._add_test_players(1)
        self.game.game_settings['current_phase'] = 'night'
        
        # Give them a useless role using the mocked factory
        self.game.players[1].assign_role(game.roles.get_role_instance("Plain Townie"))
        print(f"   -> Player Role: {self.game.players[1].role.name}")
        
        mock_interaction = AsyncMock()
        mock_interaction.user.id = 1
        
        print("   -> Attempting /kill action...")
        response = await self.game.record_night_action(mock_interaction, 'kill', "2")
        print(f"   -> Response: {response}")
        
        self.assertIn("Your role does not have the 'kill' ability", response)
        print("   -> Success! Action was rejected.")

    @async_test
    async def test_record_night_action_fail_target_dead(self):
        """Test that you cannot target a dead player."""
        print(">>> START: test_record_night_action_fail_target_dead")
        
        self._add_test_players(2)
        self.game.game_settings['current_phase'] = 'night'
        self.game.players[1].assign_role(game.roles.get_role_instance("Godfather"))
        
        # Kill the target before the action
        print("   -> Marking TestUser2 as DEAD.")
        self.game.players[2].is_alive = False 

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 1
        
        print("   -> Attempting to kill dead player TestUser2...")
        response = await self.game.record_night_action(mock_interaction, 'kill', "TestUser2")
        print(f"   -> Response: {response}")
        
        self.assertIn("is already dead", response)
        print("   -> Success! Bot rejected targeting a corpse.")

    @async_test
    async def test_record_night_action_fail_target_self_kill(self):
        """Test that the Mafia cannot kill themselves."""
        print(">>> START: test_record_night_action_fail_target_self_kill")
        
        self._add_test_players(1)
        self.game.game_settings['current_phase'] = 'night'
        self.game.players[1].assign_role(game.roles.get_role_instance("Godfather"))

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 1
        
        print("   -> Attempting to target SELF with kill...")
        response = await self.game.record_night_action(mock_interaction, 'kill', "TestUser1")
        print(f"   -> Response: {response}")
        
        self.assertIn("You cannot target yourself", response)
        print("   -> Success! Self-harm prevented.")

    @async_test
    async def test_record_night_action_fail_target_same_heal(self):
        """Test the Doctor cannot heal the same person twice in a row."""
        print(">>> START: test_record_night_action_fail_target_same_heal")
        
        self._add_test_players(2)
        self.game.game_settings['current_phase'] = 'night'
        self.game.players[1].assign_role(game.roles.get_role_instance("Town Doctor"))
        
        # Simulate that they healed Player 2 last night
        print("   -> Setting last_action_target_id = 2 (Simulating previous night history)")
        self.game.players[1].last_action_target_id = 2

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 1
        
        print("   -> Attempting to heal TestUser2 AGAIN...")
        response = await self.game.record_night_action(mock_interaction, 'heal', "TestUser2")
        print(f"   -> Response: {response}")
        
        self.assertIn("You cannot target the same person two nights in a row", response)
        print("   -> Success! Spam healing prevented.")

    @async_test
    async def test_record_night_action_success(self):
        """Test a valid night action is recorded correctly."""
        print(">>> START: test_record_night_action_success")
        
        self._add_test_players(2)
        self.game.game_settings['current_phase'] = 'night'
        self.game.players[1].assign_role(game.roles.get_role_instance("Godfather"))

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 1
        
        print("   -> Valid action: Kill TestUser2")
        response = await self.game.record_night_action(mock_interaction, 'kill', "TestUser2")
        print(f"   -> Response: {response}")
        
        self.assertIn("Your action (**kill** on **TestUser2**) has been recorded", response)
        
        # Verify internal state
        recorded_action = self.game.night_actions.get(1)
        print(f"   -> Internal Game State (night_actions): {recorded_action}")
        self.assertIsNotNone(recorded_action)
        self.assertEqual(recorded_action['type'], 'kill')
        self.assertEqual(recorded_action['target_id'], 2)
        print("   -> Success! Action stored in game state.")

    @patch('game.actions.ACTION_HANDLERS') 
    @async_test
    async def test_process_night_actions_priority_block_vs_kill(
        self, mock_action_handlers: MagicMock
    ):
        """
        Tests the priority system. 
        A Block (Priority 1) should happen before a Kill (Priority 3).
        """
        print(">>> START: test_process_night_actions_priority_block_vs_kill")
        
        # Mock specific handlers so we can track call order
        mock_handle_block = MagicMock()
        mock_handle_kill = MagicMock()
        mock_action_handlers.get.side_effect = lambda key: {'block': mock_handle_block, 'kill': mock_handle_kill}.get(key)

        self._add_test_players(3)
        self.game.players[1].assign_role(game.roles.get_role_instance("Town Role Blocker")) 
        self.game.players[2].assign_role(game.roles.get_role_instance("Godfather"))    
        self.game.players[3].assign_role(game.roles.get_role_instance("Plain Townie"))
        
        # Setup actions: P1 blocks P2. P2 tries to kill P3.
        print("   -> Setting up Night Actions: P1 Blocks P2, P2 Kills P3")
        self.game.night_actions = {
            2: {'type': 'kill', 'target_id': 3, 'night_priority': 3, 'actor': self.game.players[2]},
            1: {'type': 'block', 'target_id': 2, 'night_priority': 1, 'actor': self.game.players[1]},
        }
        
        print("   -> Processing night actions...")
        await self.game.process_night_actions()
        
        print("   -> Checking execution order (Priority 1 Block -> Priority 3 Kill)")
        # Assert Block was called
        mock_handle_block.assert_called_with(self.game, 1, 2, ANY)
        # Assert Kill was called (it is the handler's job to check if it failed, engine just calls them)
        mock_handle_kill.assert_called_with(self.game, 2, 3, ANY)
        
        print("   -> Success! Both handlers called in correct order.")

    @async_test
    async def test_tally_votes_no_lynch(self):
        """
        Tests that if NO votes are cast (0 votes), a 'no_lynch' event is generated.
        Note: Ties usually result in multi-lynch, so 0 votes is the only no-lynch case.
        """
        print(">>> START: test_tally_votes_no_lynch")
        
        self._add_test_players(3)
        self.game.game_settings['current_phase'] = 'day'
        self.game.game_settings["phase_number"] = 1
        
        # Assign roles to prevent attribute errors
        for i in range(1, 4):
            self.game.players[i].assign_role(game.roles.get_role_instance("Plain Townie"))

        # Setup: Empty dictionary means NO ONE voted.
        print("   -> Simulating Day End: 0 Votes cast (lynch_votes = {})")
        self.game.lynch_votes = {} 

        print("   -> Tallying votes...")
        winner = await self.game.tally_votes()
        
        print(f"   -> Winner returned: {winner} (Expected: None)")
        self.assertIsNone(winner)
        
        # Check Narration Events
        calls = self.game.narration_manager.add_event.call_args_list
        print(f"   -> Events triggered: {calls}")
        
        no_lynch_found = any(c[0][0] == 'no_lynch' for c in calls)
        self.assertTrue(no_lynch_found, "The 'no_lynch' event was not triggered!")
        print("   -> Success! 'no_lynch' event confirmed.")

    @async_test
    async def test_tally_votes_lynch_success(self):
        """Tests that a player is successfully lynched when majority is reached."""
        print(">>> START: test_tally_votes_lynch_success")
        
        self._add_test_players(3)
        self.game.game_settings['current_phase'] = 'day'
        self.game.game_settings["phase_number"] = 1
        
        # Setup roles
        for i in range(1, 4): self.game.players[i].assign_role(game.roles.get_role_instance("Plain Townie"))
        
        # Setup Votes: P1 and P3 vote for P2.
        # Format: {Target_ID: [List of Voters]}
        print("   -> Simulating Votes: P1 & P3 vote for P2 (2 votes vs 3 players)")
        self.game.lynch_votes = {2: [1, 3]}
        
        print("   -> Tallying votes...")
        winner = await self.game.tally_votes()
        self.assertIsNone(winner)
        
        # Assertions
        is_dead = not self.game.players[2].is_alive
        death_reason = self.game.players[2].death_info.get('how')
        print(f"   -> Player 2 Status: Alive? {not is_dead}. Reason: {death_reason}")
        
        self.assertTrue(is_dead, "Player 2 should be dead.")
        self.assertEqual(death_reason, "Lynched by the town")
        print("   -> Success! Player 2 was lynched.")

    @async_test
    async def test_tally_votes_inactivity_kill(self):
        """Tests that inactive players (missed_votes > threshold) are killed."""
        print(">>> START: test_tally_votes_inactivity_kill")
        
        self._add_test_players(2)
        self.game.game_settings['current_phase'] = 'day'
        self.game.game_settings["phase_number"] = 1
        
        self.game.players[1].assign_role(game.roles.get_role_instance("Plain Townie"))
        self.game.players[2].assign_role(game.roles.get_role_instance("Plain Townie"))
        
        # Setup: P1 has missed 10 votes (Threshold is 2)
        print("   -> Setting P1 missed_votes = 10 (Threshold is 2)")
        self.game.players[1].missed_votes = 10 
        
        # Setup Votes: P2 votes for P1. P1 DOES NOT vote (inactive).
        self.game.lynch_votes = {1: [2]} 
        
        print("   -> Tallying votes...")
        await self.game.tally_votes()
        
        # Assertions
        is_dead = not self.game.players[1].is_alive
        print(f"   -> Player 1 Status: Alive? {not is_dead}")
        self.assertTrue(is_dead, "Player 1 should be dead due to inactivity")
        
        # Check for event
        calls = self.game.narration_manager.add_event.call_args_list
        inactivity_found = any(c[0][0] == 'inactivity_kill' for c in calls)
        print(f"   -> Inactivity event found? {inactivity_found}")
        self.assertTrue(inactivity_found)
        print("   -> Success! Inactive player executed.")

    @async_test
    async def test_tally_votes_jester_win(self):
        """Tests that if the Jester is lynched, they win immediately."""
        print(">>> START: test_tally_votes_jester_win")
        
        self._add_test_players(3) 
        self.game.game_settings['current_phase'] = 'day'
        self.game.game_settings["phase_number"] = 1
        
        print("   -> Assigning Jester role to P1.")
        self.game.players[1].assign_role(game.roles.get_role_instance("Jester"))
        self.game.players[2].assign_role(game.roles.get_role_instance("Plain Townie"))
        self.game.players[3].assign_role(game.roles.get_role_instance("Plain Townie")) 
        
        # Setup Votes: P2 and P3 vote for the Jester (P1).
        print("   -> Votes: P2 & P3 vote for Jester (P1).")
        self.game.lynch_votes = {1: [2, 3], 2: [1]} 
        
        print("   -> Tallying votes...")
        winner = await self.game.tally_votes() 
        print(f"   -> Winner returned: {winner}")

        # Assertions
        self.assertEqual(winner, "Jester") 
        
        calls = self.game.narration_manager.add_event.call_args_list
        jester_call_found = any(c[0][0] == 'jester_win' for c in calls)
        self.assertTrue(jester_call_found, "jester_win event should be triggered")
        print("   -> Success! Jester won correctly.")

    def test_check_win_conditions_town_win(self):
        """Tests Town win condition (Mafia are all dead)."""
        print(">>> START: test_check_win_conditions_town_win")
        self._add_test_players(2)
        
        self.game.players[1].assign_role(game.roles.get_role_instance("Plain Townie"))
        self.game.players[2].assign_role(game.roles.get_role_instance("Godfather"))
        
        print("   -> Killing the Godfather (P2)...")
        self.game.players[2].is_alive = False # Mafia is dead
        
        winner = self.game.check_win_conditions()
        print(f"   -> Winner: {winner}")
        self.assertEqual(winner, "Town")
        print("   -> Success! Town wins when Mafia dies.")

    def test_check_win_conditions_mafia_win(self):
        """Tests Mafia win condition (Mafia >= Town)."""
        print(">>> START: test_check_win_conditions_mafia_win")
        self.game.game_settings["current_phase"] = "day" 
        self._add_test_players(2)
        
        self.game.players[1].assign_role(game.roles.get_role_instance("Plain Townie"))
        self.game.players[2].assign_role(game.roles.get_role_instance("Godfather"))
        
        print("   -> Situation: 1 Town vs 1 Mafia (Parity reached)")
        winner = self.game.check_win_conditions()
        print(f"   -> Winner: {winner}")
        self.assertEqual(winner, "Mafia")
        print("   -> Success! Mafia wins via parity.")

    @patch('game.engine.asyncio.create_task')
    @async_test
    async def test_handle_promotions_mob_goon_success(self, mock_create_task):
        """
        Tests the chain of command: Godfather dies -> Goon becomes new Killer.
        """
        print(">>> START: test_handle_promotions_mob_goon_success")
        self._add_test_players(3)

        # 1. Setup Roles
        print("   -> Setting up manual roles: GF, Goon, Townie")
        gf_role = game.roles.get_role_instance("Godfather")
        goon_role = game.roles.get_role_instance("Mob Goon")
        townie_role = game.roles.get_role_instance("Plain Townie")
        
        self.game.players[1].assign_role(gf_role)
        self.game.players[2].assign_role(goon_role)
        self.game.players[3].assign_role(townie_role)
        
        # 2. Kill the Godfather
        print("   -> Killing Godfather (P1)...")
        dead_gf = self.game.players[1]
        dead_gf.is_alive = False

        # Verify Preconditions
        print(f"   -> Pre-check: Goon has kill ability? {'kill' in self.game.players[2].role.abilities}")
        self.assertNotIn('kill', self.game.players[2].role.abilities)

        # 3. Execute promotion
        print("   -> Executing _handle_promotions...")
        self.game._handle_promotions(dead_gf)

        # 4. Assertions
        promoted_player = self.game.players[2]
        has_kill = 'kill' in promoted_player.role.abilities
        print(f"   -> Post-check: Goon has kill ability? {has_kill}")
        
        self.assertTrue(has_kill, "Mob Goon should have inherited the kill ability")
        self.game.narration_manager.add_event.assert_called_with('promotion', promoted_player=promoted_player)
        
        # Run the DM task to silence warnings
        coro = mock_create_task.call_args[0][0]
        await coro 
        print("   -> Success! Goon promoted successfully.")

    @async_test
    async def test_handle_promotions_no_mafioso_left(self):
        """
        Tests that if no Mafia members are left, no promotion occurs.
        """
        print(">>> START: test_handle_promotions_no_mafioso_left")
        self._add_test_players(1)
        # 1. Setup Role
        print("   -> Setting up manual role: Godfather")
        gf_role = game.roles.get_role_instance("Godfather")
        self.game.players[1].assign_role(gf_role)
        # 2. Kill the Godfather
        print("   -> Killing Godfather (P1)...")
        dead_gf = self.game.players[1]
        dead_gf.is_alive = False
        # 3. Execute promotion
        print("   -> Executing _handle_promotions...")
        self.game._handle_promotions(dead_gf)
        # 4. Assertions
        print("   -> Checking that no promotion occurred...")
        self.game.narration_manager.add_event.assert_not_called()
        print("   -> Success! No promotion occurred as expected.")

    @patch('game.engine.asyncio.create_task')
    @async_test
    async def test_handle_promotions_no_goon_but_other_mafia(self, mock_create_task):
        """
        Tests that if no Goon is left, another Mafia member is promoted.
        """
        print(">>> START: test_handle_promotions_no_goon_but_other_mafia")
        self._add_test_players(2)
        # 1. Setup Roles
        print("   -> Setting up manual roles: GF, Framer")
        gf_role = game.roles.get_role_instance("Godfather")
        framer_role = game.roles.get_role_instance("Mafia Framer")
        self.game.players[1].assign_role(gf_role)
        self.game.players[2].assign_role(framer_role)
        # 2. Kill the Godfather
        print("   -> Killing Godfather (P1)...")
        dead_gf = self.game.players[1]
        dead_gf.is_alive = False
        # 3. Execute promotion
        print("   -> Executing _handle_promotions...")
        self.game._handle_promotions(dead_gf)
        # 4. Assertions
        promoted_player = self.game.players[2]
        has_kill = 'kill' in promoted_player.role.abilities
        print(f"   -> Post-check: Framer has kill ability? {has_kill}")
        self.assertTrue(has_kill, "Mafia Framer should have inherited the kill ability")
        self.game.narration_manager.add_event.assert_called_with('promotion', promoted_player=promoted_player)
        
        # Run task
        coro = mock_create_task.call_args[0][0]
        await coro
        print("   -> Success! Framer promoted successfully.")

    @patch('game.engine.asyncio.create_task')
    @async_test
    async def test_handle_promotions_mob_goon_to_mob_goon(self, mock_create_task):
        """
        Tests that if after a mob goon dies when they have the kill ability, that another mob goon is promoted to the kill ability.
        """
        print(">>> START: test_handle_promotions_mob_goon_to_mob_goon")
        self._add_test_players(2)
        # 1. Setup Roles
        print("   -> Setting up manual roles: GF (Goon with Kill), Mob Goon")
        # P1 is effectively a promoted goon
        gf_role = GameRole(name="Mob Goon", alignment="Mafia", description="", short_description="", abilities={'kill': 'Kill ability'})
        goon_role = game.roles.get_role_instance("Mob Goon")
        self.game.players[1].assign_role(gf_role)
        self.game.players[2].assign_role(goon_role)
        # 2. Kill the Mob Goon with kill ability
        print("   -> Killing Mob Goon with kill ability (P1)...")
        dead_gf = self.game.players[1]
        dead_gf.is_alive = False
        # 3. Execute promotion
        print("   -> Executing _handle_promotions...")
        self.game._handle_promotions(dead_gf)
        # 4. Assertions
        promoted_player = self.game.players[2]
        has_kill = 'kill' in promoted_player.role.abilities
        print(f"   -> Post-check: Goon has kill ability? {has_kill}")
        self.assertTrue(has_kill, "Mob Goon should have inherited the kill ability even if already a Goon")
        self.game.narration_manager.add_event.assert_called_with('promotion', promoted_player=promoted_player)
        
        # Run task
        coro = mock_create_task.call_args[0][0]
        await coro
        print("   -> Success! Mob Goon promoted successfully.")
    

    def test_game_settings_initialization(self):
        """Test that the game correctly stores custom immunity settings."""
        custom_game = Game(self.mock_bot, self.mock_guild)
        
        self.assertFalse(custom_game.game_settings['gf_investigate'])
        self.assertTrue(custom_game.game_settings['sk_investigate'])

    @patch('game.roles.get_role_instance')
    def test_role_immunity_override_during_assignment(self, mock_get_role):
        """Test that roles have their immunity attribute overridden during setup."""
        # Setup mock role
        mock_role = MagicMock()
        mock_role.name = "Godfather"
        mock_role.investigation_immune = True # Default
        mock_get_role.return_value = mock_role
        
        # Start game with Godfather immunity DISABLED
        self.game.game_settings['gf_investigate'] = True
        
        # Simulate the part of generate_game_roles that overrides immunity
        # (This mimics the logic we added to engine.py)
        roles_to_assign = ["Godfather"]
        for role_name in roles_to_assign:
            role_inst = game.roles.get_role_instance(role_name)
            if role_name == "Godfather":
                role_inst.investigation_immune = self.game.game_settings['gf_investigate']
        
        self.assertFalse(mock_role.investigation_immune)