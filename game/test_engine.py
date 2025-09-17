import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call
from datetime import datetime, timezone, timedelta

# It's good practice to set up the path if running tests from the root directory
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        self.mock_cleanup = MagicMock()

        # Mock file loading to prevent actual I/O
        with patch('game.engine.load_data') as self.mock_load_data:
            self.mock_load_data.side_effect = self.mock_load_data_side_effect
            self.game = Game(self.mock_bot, self.mock_guild, self.mock_cleanup)

    def mock_load_data_side_effect(self, filepath, error_default=None):
        """Simulate loading data from files."""
        if "discord_roles.json" in filepath:
            return {"mod": {"id": 123}, "living": {"id": 456}, "dead": {"id": 789}}
        if "bot_names.txt" in filepath:
            return ["NPC1", "NPC2", "NPC3"]
        if "rules.txt" in filepath:
            return ["Rule 1", "Rule 2"]
        if "mafia_setups.json" in filepath:
            return {
                "2": [
                    {
                        "id": "2p_test",
                        "roles": [{"name": "Townie", "quantity": 1}, {"name": "Godfather", "quantity": 1}]
                    }
                ]
            }
        return {} if ".json" in filepath else []

    def _add_test_players(self, count):
        """Helper to add a number of mock players to the game."""
        for i in range(1, count + 1):
            user = MagicMock()
            user.id = i
            user.name = f"TestUser{i}"
            self.game.players[user.id] = Player(user_id=user.id, discord_name=user.name, display_name=f"Player {i}")

    @async_test
    async def test_add_player_success(self):
        """Test successfully adding a player during the signup phase."""
        self.game.game_settings["current_phase"] = "signup"
        mock_user = MagicMock(id=1, name="TestUser")
        mock_channel = AsyncMock()

        with patch('game.engine.update_player_discord_roles', new_callable=AsyncMock):
            await self.game.add_player(mock_user, "Player 1", mock_channel)

        self.assertIn(1, self.game.players)
        self.assertEqual(self.game.players[1].display_name, "Player 1")
        mock_channel.send.assert_any_call("Welcome to the game, **Player 1**! You are player #1.")

    @async_test
    async def test_add_player_already_joined(self):
        """Test adding a player who has already joined."""
        self.game.game_settings["current_phase"] = "signup"
        self._add_test_players(1) # Add player with id=1
        mock_user = MagicMock(id=1, name="TestUser")
        mock_channel = AsyncMock()

        await self.game.add_player(mock_user, "Player 1", mock_channel)

        self.assertEqual(len(self.game.players), 1)
        mock_channel.send.assert_called_with("You have already joined the game!")

    @async_test
    async def test_remove_player_success(self):
        """Test successfully removing a player during signup."""
        self.game.game_settings["current_phase"] = "signup"
        self._add_test_players(1)
        mock_user = MagicMock(id=1)
        mock_channel = AsyncMock()

        with patch('game.engine.update_player_discord_roles', new_callable=AsyncMock):
            await self.game.remove_player(mock_user, mock_channel)

        self.assertNotIn(1, self.game.players)
        mock_channel.send.assert_called_with("**Player 1** has left the game.")

    @patch('game.roles.get_role_instance')
    def test_generate_game_roles_classic(self, mock_get_role):
        """Test role generation for a classic game with a valid setup."""
        mock_get_role.side_effect = lambda name: MagicMock(name=name)
        self._add_test_players(2)
        self.game.game_settings['game_type'] = "classic"

        self.game.generate_game_roles()

        self.assertEqual(len(self.game.game_roles), 2)
        role_names = sorted([r.name for r in self.game.game_roles])
        self.assertEqual(role_names, ["Godfather", "Townie"])

    @patch('game.roles.get_role_instance')
    def test_generate_game_roles_battle_royale(self, mock_get_role):
        """Test role generation for battle royale mode."""
        mock_get_role.return_value = MagicMock(name="Vigilante")
        self._add_test_players(5)
        self.game.game_settings['game_type'] = "battle_royale"

        self.game.generate_game_roles()

        self.assertEqual(len(self.game.game_roles), 5)
        self.assertTrue(all(r.name == "Vigilante" for r in self.game.game_roles))

    @async_test
    async def test_process_lynch_vote_success(self):
        """Test a valid lynch vote during the day phase."""
        self.game.game_settings["current_phase"] = "day"
        self._add_test_players(2) # Adds players 1 and 2
        mock_voter_user = MagicMock(id=1)
        target_name = "Player 2"
        
        with patch('game.engine.Game.send_vote_count', new_callable=AsyncMock):
            result = await self.game.process_lynch_vote(MagicMock(), mock_voter_user, target_name)

        self.assertEqual(result, "Your vote for **Player 2** has been recorded.")
        self.assertIn(2, self.game.lynch_votes)
        self.assertIn(1, self.game.lynch_votes[2])

    @async_test
    async def test_tally_votes_jester_win(self):
        """Test that lynching a Jester results in a Jester win."""
        with patch('game.roles.ALL_ROLES_DATA', {"Jester": {"base": "NeutralEvil"}}):
            jester_role = get_role_instance("Jester")

        self.game.game_settings["current_phase"] = "day"
        self._add_test_players(2)
        self.game.players[1].assign_role(jester_role)
        self.game.players[2].assign_role(get_role_instance("Townie"))

        # Player 2 votes for Player 1 (the Jester)
        self.game.lynch_votes = {1: [2]}

        winner = await self.game.tally_votes()

        self.assertEqual(winner, "Jester")
        # Check that the narration event was added
        self.assertEqual(self.game.narration_manager.events[0]['type'], 'jester_win')
        self.assertEqual(self.game.narration_manager.events[0]['victim'].id, 1)

    def test_check_win_conditions_town_win(self):
        """Test town win condition: all mafia are dead."""
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Townie"))
        self.game.players[2].assign_role(get_role_instance("Godfather"))
        self.game.players[2].is_alive = False # Mafia is dead

        winner = self.game.check_win_conditions()
        self.assertEqual(winner, "Town")

    def test_check_win_conditions_mafia_win(self):
        """Test mafia win condition: mafia outnumber town."""
        self.game.game_settings["current_phase"] = "day"
        self._add_test_players(2)
        self.game.players[1].assign_role(get_role_instance("Townie"))
        self.game.players[2].assign_role(get_role_instance("Godfather"))

        # Mafia and Town are equal, but no protective roles exist
        winner = self.game.check_win_conditions()
        self.assertEqual(winner, "Mafia")

    def test_check_win_conditions_draw(self):
        """Test draw condition: no players are left alive."""
        self._add_test_players(2)
        self.game.players[1].is_alive = False
        self.game.players[2].is_alive = False

        winner = self.game.check_win_conditions()
        self.assertEqual(winner, "Draw")

if __name__ == '__main__':
    unittest.main()
