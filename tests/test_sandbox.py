# tests/test_sandbox.py
import unittest
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_0_logging import setup_test_logging
from sandbox import GameSandbox, ScenarioSuite, run_full_simulation

logger = setup_test_logging()


class TestGameSandbox(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the GameSandbox harness, mock Discord layer, and scenarios."""

    async def asyncSetUp(self):
        self.sandbox = GameSandbox(game_type="classic", player_names=["Alice", "Bob", "Charlie", "Dave"])

    def test_sandbox_initialization(self):
        """Test sandbox properly sets up players and mock Discord environment."""
        self.assertEqual(len(self.sandbox.game.players), 4)
        self.assertIsNotNone(self.sandbox.get_player("Alice"))
        self.assertIsNotNone(self.sandbox.get_player("Bob"))
        self.assertIsNone(self.sandbox.get_player("NonExistent"))

        # Test adding NPC
        npc = self.sandbox.add_npc("Bot1")
        self.assertTrue(npc.is_npc)
        self.assertEqual(len(self.sandbox.game.players), 5)

        # Test removing player
        removed = self.sandbox.remove_player("Bot1")
        self.assertTrue(removed)
        self.assertEqual(len(self.sandbox.game.players), 4)

    def test_manual_and_auto_role_assignment(self):
        """Test assigning roles manually and using the auto role generator."""
        # Manual assignment
        success = self.sandbox.set_player_role("Alice", "Godfather")
        self.assertTrue(success)
        alice = self.sandbox.get_player("Alice")
        self.assertEqual(alice.role.name, "Godfather")
        self.assertEqual(alice.role.alignment, "Mafia")

        # Invalid role name
        fail = self.sandbox.set_player_role("Alice", "SuperHero")
        self.assertFalse(fail)

        # Auto assignment
        assigned = self.sandbox.auto_assign_roles()
        self.assertEqual(len(assigned), 4)
        for p in self.sandbox.game.players.values():
            self.assertIsNotNone(p.role)

    async def test_day_phase_voting_and_lynch(self):
        """Test daytime vote casting, tallying, and lynch execution."""
        self.sandbox.set_player_role("Alice", "Godfather")
        self.sandbox.set_player_role("Bob", "Plain Townie")
        self.sandbox.set_player_role("Charlie", "Plain Townie")
        self.sandbox.set_player_role("Dave", "Plain Townie")

        self.sandbox.start_day(1)
        self.assertEqual(self.sandbox.game.game_settings["current_phase"], "day")

        # Cast votes on Alice
        await self.sandbox.cast_vote("Bob", "Alice")
        await self.sandbox.cast_vote("Charlie", "Alice")
        await self.sandbox.cast_vote("Dave", "Alice")

        tally = self.sandbox.get_vote_tally()
        self.assertIn("Alice", tally["tally"])
        self.assertEqual(tally["tally"]["Alice"]["count"], 3)
        self.assertIn("Alice", tally["not_voted"])  # Alice did not vote

        # End day and resolve lynch
        day_res = await self.sandbox.resolve_day()
        alice = self.sandbox.get_player("Alice")
        self.assertFalse(alice.is_alive)
        self.assertIn(alice, day_res["deaths"])
        self.assertEqual(day_res["winner"], "Town")

    async def test_night_phase_actions(self):
        """Test night action recording, priority resolution, and death processing."""
        self.sandbox.set_player_role("Alice", "Godfather")
        self.sandbox.set_player_role("Bob", "Town Doctor")
        self.sandbox.set_player_role("Charlie", "Plain Townie")
        self.sandbox.set_player_role("Dave", "Plain Townie")

        self.sandbox.start_night(1)
        self.assertEqual(self.sandbox.game.game_settings["current_phase"], "night")

        # Mafia targets Charlie, Doctor protects Charlie
        await self.sandbox.record_action("Alice", "kill", "Charlie")
        await self.sandbox.record_action("Bob", "heal", "Charlie")

        queued = self.sandbox.get_queued_actions()
        self.assertEqual(len(queued), 2)

        night_res = await self.sandbox.resolve_night()
        charlie = self.sandbox.get_player("Charlie")
        self.assertTrue(charlie.is_alive)
        self.assertEqual(len(night_res["deaths"]), 0)

    async def test_all_preset_scenarios(self):
        """Verify that all pre-packaged scenarios execute and pass successfully."""
        self.assertTrue(await ScenarioSuite.doctor_saves_target())
        self.assertTrue(await ScenarioSuite.roleblock_prevents_kill())
        self.assertTrue(await ScenarioSuite.cop_investigates())
        self.assertTrue(await ScenarioSuite.jester_lynch())
        self.assertTrue(await ScenarioSuite.godfather_promotion())
        self.assertTrue(await ScenarioSuite.inactivity_death())
        self.assertTrue(await ScenarioSuite.town_victory())
        self.assertTrue(await ScenarioSuite.mafia_victory())

    async def test_full_simulation_run(self):
        """Verify full automated simulation completes cleanly."""
        winner = await run_full_simulation(num_players=5, max_rounds=10)
        self.assertIsNotNone(winner)


if __name__ == '__main__':
    unittest.main()
