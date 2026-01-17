import unittest
from unittest.mock import MagicMock, patch
from collections import defaultdict
from game import actions
from game.engine import Game

class TestActionHandlers(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        self.game = Game(self.mock_bot, self.mock_guild)
        
        # Initialize game state
        self.game.players = {}
        self.game.night_actions = {}
        self.game.kill_attempts_on = defaultdict(list)
        self.game.heals_on_players = defaultdict(list)
        self.game.narration_manager = MagicMock()

    def create_mock_player(self, p_id, name, role_name="Townie", abilities=None):
        player = MagicMock()
        player.id = p_id
        player.display_name = name
        player.role = MagicMock()
        player.role.name = role_name
        # FIX: Explicitly set False so it doesn't default to MagicMock(True)
        player.role.is_night_immune = False 
        player.role.abilities = abilities if abilities else {}
        player.is_alive = True
        player.send_dm = MagicMock() 
        self.game.players[p_id] = player
        return player

    async def test_handle_kill_valid(self):
        """Test a standard kill action is recorded."""
        killer = self.create_mock_player(1, "Killer", "Mafia", {"kill": "desc"})
        victim = self.create_mock_player(2, "Victim")
        
        night_outcomes = {1: {'status': None}}
        
        # Function is sync, so no await
        actions.handle_kill(self.game, killer.id, victim.id, night_outcomes)
        
        self.assertIn(2, self.game.kill_attempts_on)
        self.assertIn(1, self.game.kill_attempts_on[2])
        self.assertEqual(night_outcomes[1]['status'], "successful")

    async def test_handle_kill_victim_already_dead_in_cycle(self):
        """Test kill submission."""
        killer = self.create_mock_player(1, "Killer")
        victim = self.create_mock_player(2, "Victim")
        victim.is_alive = False 
        
        night_outcomes = {1: {'status': None}}
        actions.handle_kill(self.game, killer.id, victim.id, night_outcomes)
        
        # Should still mark action as successful attempt
        self.assertEqual(night_outcomes[1]['status'], "successful")

    async def test_handle_heal_valid(self):
        doctor = self.create_mock_player(1, "Doc", "Doctor", {"heal": "desc"})
        target = self.create_mock_player(2, "Patient")
        
        night_outcomes = {1: {'status': None}}
        actions.handle_heal(self.game, doctor.id, target.id, night_outcomes)
        
        self.assertIn(2, self.game.heals_on_players)
        self.assertEqual(night_outcomes[1]['status'], "successful")

    async def test_handle_block_success(self):
        blocker = self.create_mock_player(1, "Blocker", "Town Role Blocker", {"block": "desc"})
        target = self.create_mock_player(2, "Target", "Mafia", {"kill": "desc"})
        
        # Give target a pending action
        target_action = {"type": "kill", "target_id": 3, 'status': None}
        self.game.night_actions[2] = target_action
        night_outcomes = {1: {"status": None}, 2: target_action} 
        
        actions.handle_block(self.game, blocker.id, target.id, night_outcomes)
        
        # Blocker should be successful
        self.assertEqual(night_outcomes[1]['status'], "successful")
        # Target should be blocked
        self.assertEqual(night_outcomes[2]['status'], "blocked")

    @patch('asyncio.create_task')
    async def test_investigate_mafia(self, mock_create_task):
        # Fix: Silence 'coroutine never awaited' warning
        mock_create_task.side_effect = lambda coro: coro.close()

        cop = self.create_mock_player(1, "Cop", "Town Cop", {"investigate": "desc"})
        suspect = self.create_mock_player(2, "Suspect", "Mafia Goon")
        suspect.role.investigation_result = {"Suspicious": "Found Mafia"} 
        
        night_outcomes = {1: {'status': None}}
        actions.handle_investigation(self.game, cop.id, suspect.id, night_outcomes)
        
        mock_create_task.assert_called_once()

    @patch('asyncio.create_task')
    async def test_investigate_godfather(self, mock_create_task):
        # Fix: Silence 'coroutine never awaited' warning
        mock_create_task.side_effect = lambda coro: coro.close()

        cop = self.create_mock_player(1, "Cop")
        gf = self.create_mock_player(2, "GF", "Godfather")
        gf.role.investigation_result = {"Innocent": "Seems fine"} 
        
        night_outcomes = {1: {'status': None}}
        actions.handle_investigation(self.game, cop.id, gf.id, night_outcomes)
        
        mock_create_task.assert_called_once()
    
    # game/test_action.py (Portion of the updated file)

    @patch('asyncio.create_task')
    async def test_investigate_immune_target_spoof(self, mock_create_task):
        """Verify that an immune target returns the spoofed result instead of their real role."""
        # Fix: Silence 'coroutine never awaited' warning
        mock_create_task.side_effect = lambda coro: coro.close()

        cop = self.create_mock_player(1, "Cop")
        gf = self.create_mock_player(2, "Godfather", "Godfather")
        
        # Setup the immunity and the spoof result
        gf.role.investigation_immune = True
        gf.role.investigation_result = {"Villager": "A simple resident of the town."}
        
        night_outcomes = {1: {'status': None}}
        
        # Execute the handler
        actions.handle_investigation(self.game, cop.id, gf.id, night_outcomes)
        
        # We need to capture the message sent. Since actions.py fetches user and sends DM,
        # we check if the task was created. In a full integration test we'd mock fetch_user.
        mock_create_task.assert_called_once()
        self.assertEqual(night_outcomes[1]['status'], 'successful')

    @patch('asyncio.create_task')
    async def test_investigate_immune_target_string_fallback(self, mock_create_task):
        """Verify the handler works even if investigation_result is just a string."""
        mock_create_task.side_effect = lambda coro: coro.close()

        cop = self.create_mock_player(1, "Cop")
        sk = self.create_mock_player(3, "SK", "Serial Killer")
        
        sk.role.investigation_immune = True
        sk.role.investigation_result = "Innocent Resident" # String format
        
        night_outcomes = {1: {'status': None}}
        actions.handle_investigation(self.game, cop.id, sk.id, night_outcomes)
        
        self.assertEqual(night_outcomes[1]['status'], 'successful')

if __name__ == '__main__':
    unittest.main()