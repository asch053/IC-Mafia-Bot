import unittest
from unittest.mock import MagicMock, patch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from game.engine.initialise import initialize_game

class TestBotNamesFallback(unittest.TestCase):
    def setUp(self):
        self.mock_game = MagicMock()
        self.mock_game.max_players = 19
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()

    @patch("game.engine.initialise.os.path.exists", return_value=False)
    def test_missing_bot_names_file_triggers_critical_and_generates_fallback(self, mock_exists):
        with self.assertLogs("game.engine.initialise", level="CRITICAL") as log_capture:
            initialize_game(self.mock_game, self.mock_bot, self.mock_guild)
            
        self.assertTrue(any("CRITICAL ERROR: Failed to load NPC bot names" in record for record in log_capture.output))
        self.assertTrue(hasattr(self.mock_game, "npc_names"))
        self.assertGreaterEqual(len(self.mock_game.npc_names), 38)
        self.assertTrue(self.mock_game.npc_names[0].startswith("Bot_"))
        self.assertEqual(self.mock_game.npc_names[0], "Bot_01")
        self.assertEqual(self.mock_game.npc_names[1], "Bot_02")

    @patch("game.engine.initialise.os.path.exists", return_value=True)
    @patch("game.engine.initialise.load_data", return_value=[])
    def test_empty_bot_names_file_triggers_fallback(self, mock_load, mock_exists):
        with self.assertLogs("game.engine.initialise", level="CRITICAL") as log_capture:
            initialize_game(self.mock_game, self.mock_bot, self.mock_guild)
            
        self.assertTrue(any("CRITICAL ERROR" in record for record in log_capture.output))
        self.assertEqual(self.mock_game.npc_names[0], "Bot_01")
        self.assertEqual(self.mock_game.npc_names[9], "Bot_10")

    @patch("game.engine.initialise.os.path.exists", return_value=True)
    @patch("game.engine.initialise.load_data", return_value=["Alice", "Bob", "Charlie"])
    def test_successful_bot_names_load(self, mock_load, mock_exists):
        initialize_game(self.mock_game, self.mock_bot, self.mock_guild)
        self.assertEqual(self.mock_game.npc_names, ["Alice", "Bob", "Charlie"])

if __name__ == "__main__":
    unittest.main()
