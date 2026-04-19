import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import json
import os
import sys
import logging

# 1. Initialize Test Logging (using your existing setup_test_logging logic)
from tests.test_0_logging import setup_test_logging
test_log = setup_test_logging()

# Add the root directory to sys.path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- 2. CONFIGURATION MOCKING ---
# We mock the config module globally to avoid errors during imports
mock_config = MagicMock()
mock_config.LIVING_ROLE_ID = 111
mock_config.DEAD_ROLE_ID = 222
mock_config.SPECTATOR_ROLE_ID = 333
mock_config.STORIES_CHANNEL_ID = 444
mock_config.GEMINI_API_KEY = "mock_key"
mock_config.game_type = "Testing"
mock_config.min_sk_players = 9
mock_config.min_cop_players = 6
mock_config.AI_RETRY_DELAY = 0.1
mock_config.AI_MAX_RETRIES = 2
sys.modules['config'] = mock_config

# --- 3. MODULE IMPORTS ---
from game.player import Player
from game.roles import get_role_instance, ROLE_CLASSES
from game.narration_ai import _construct_ai_prompt, _generate_mechanical_summary, generate_story, _get_involved_quirks

class TestGameLogic(unittest.IsolatedAsyncioTestCase):
    """
    Comprehensive test suite for Mafia Bot Game Logic and AI Narration.
    Reports every major step to the dedicated test log file.
    """

    def setUp(self):
        """Standard environment setup for narration tests."""
        # Create dummy player objects
        self.player1 = Player(101, "Alice#0001", "Alice")
        self.player2 = Player(102, "Bob#0002", "Bob")
        
        # Manually assign roles to avoid external JSON dependencies during initialization
        self.player1.role = get_role_instance("Town Cop")
        self.player2.role = get_role_instance("Mob Goon")

        self.game_state = {
            "phase": "night",
            "number": 1,
            "story_type": "Classic Mafia",
            "game_type": "classic",
            "living_players": [self.player1, self.player2],
            "game_id": "TEST_G_001",
            "is_introduction": False,
            "is_game_over": False,
            "is_prologue": False # Added explicitly to avoid logic skipping quirks
        }

    def log_step(self, test_name, step_num, description):
        msg = f"[{test_name}] STEP {step_num}: {description}"
        test_log.info(msg)

    def log_result(self, test_name, passed, reason=None):
        status = "PASSED ✅" if passed else f"FAILED ❌ (Reason: {reason})"
        test_log.info(f"[{test_name}] RESULT: {status}")

    # --- ROLE TESTS ---

    def test_role_loading_integrity(self):
        """Tests that roles load correctly and map to the right Python classes."""
        t_name = "test_role_loading_integrity"
        self.log_step(t_name, 0, "Starting Role Verification...")
        
        try:
            self.log_step(t_name, 1, "Attempting to load 'Town Cop'...")
            cop = get_role_instance("Town Cop")
            self.assertIsNotNone(cop)
            # Verify class inheritance
            self.assertTrue(isinstance(cop, ROLE_CLASSES["TownInvestigative"]), "Town Cop is not a TownInvestigative instance")
            self.log_step(t_name, 2, f"Verified class: {type(cop).__name__}")

            self.log_step(t_name, 3, "Attempting to load 'Godfather'...")
            gf = get_role_instance("Godfather")
            self.assertEqual(gf.alignment, "Mafia")
            
            # NOTE: If this fails, ensure get_role_instance uses 'investigation_immune'
            # and matches the parameter in GameRole.__init__
            self.assertTrue(getattr(gf, 'investigation_immune', False), "Godfather failed to inherit immunity from role_definition.json")
            
            self.log_result(t_name, True)
        except Exception as e:
            self.log_result(t_name, False, str(e))
            raise

    # --- NARRATION INTEGRITY TESTS ---

    def test_mechanical_summary_formation(self):
        """Checks if the hard-coded summary formats events from Player objects correctly."""
        t_name = "test_mechanical_summary_formation"
        self.log_step(t_name, 0, "Starting Mechanical Summary Test...")

        try:
            events = [
                {'type': 'kill', 'victim': self.player1, 'killer': self.player2},
                {'type': 'save', 'victim': self.player2, 'healer': self.player1}
            ]
            self.log_step(t_name, 1, f"Feeding mock events: {len(events)} events created.")
            
            summary = _generate_mechanical_summary(events)
            self.log_step(t_name, 2, f"MAJOR OUTPUT (Mechanical Summary):\n{summary}")

            self.assertIn("Alice", summary, "Victim name missing from summary")
            self.assertIn("🔪", summary, "Kill emoji missing from summary")
            self.assertIn("❤️", summary, "Save emoji missing from summary")
            self.assertIn("Town Cop", summary, "Role name reveal missing from summary")
            
            self.log_result(t_name, True)
        except Exception as e:
            self.log_result(t_name, False, str(e))
            raise

    @patch('community.quirk_logic.get_all_approved')
    def test_quirk_integration_in_context(self, mock_quirks):
        """Verifies player quirks are correctly matched to IDs in game_state."""
        t_name = "test_quirk_integration"
        self.log_step(t_name, 0, "Starting Quirk Integration Test...")

        try:
            # Step 1: Mock Approved Quirks
            mock_quirks.return_value = {
                "101": "Obsessed with 1980s synthwave.",
                "102": "Always talks in riddles."
            }
            self.log_step(t_name, 1, "Mocking quirk logic data for Alice (101) and Bob (102).")

            # Step 2: Test 'involved quirks' logic
            # This logic filters quirks based on who is relevant this phase
            events = [{'type': 'kill', 'victim': self.player2, 'killer': self.player1}]
            quirks_output = _get_involved_quirks(self.game_state, events)
            
            self.log_step(t_name, 2, f"MAJOR OUTPUT (Quirks Context Block):\n{quirks_output}")

            # Verify that the logic successfully retrieved Alice's quirk
            self.assertIn("Alice", quirks_output, "Alice not found in quirk block")
            self.assertIn("synthwave", quirks_output, "Quirk content missing")
            
            self.log_result(t_name, True)
        except Exception as e:
            self.log_result(t_name, False, str(e))
            raise

    def test_ai_prompt_construction(self):
        """Validates that Game settings and Player names are passed correctly to the AI prompt."""
        t_name = "test_ai_prompt_construction"
        self.log_step(t_name, 0, "Starting AI Prompt Construction Test...")

        try:
            events = [{'type': 'lynch', 'victims': [self.player2]}]
            history = ["Previously, the sun set on a quiet town."]
            
            self.log_step(t_name, 1, "Calling _construct_ai_prompt with Game and Player data.")
            prompt = _construct_ai_prompt(self.game_state, events, history)
            
            # Truncate prompt for logs to keep it readable
            self.log_step(t_name, 2, f"MAJOR OUTPUT (Prompt Snippet):\n{prompt[:300]}...")

            # Use case-insensitive checks for reliability
            self.assertIn("Night 1", prompt)
            self.assertIn("Alice", prompt)
            self.assertTrue("lynch" in prompt.lower(), "Lynch event missing from prompt")
            
            self.log_result(t_name, True)
        except Exception as e:
            self.log_result(t_name, False, str(e))
            raise

    @patch('game.narration_ai.client')
    async def test_ai_generation_cycle(self, mock_ai_client):
        """Simulates a full AI call, checking for success and SDK interaction."""
        t_name = "test_ai_generation_cycle"
        self.log_step(t_name, 0, "Starting Async AI Generation Cycle...")

        try:
            # Step 1: Mock API Response
            mock_response = MagicMock()
            mock_response.text = "The shadows of the mafia stretched across the town square."
            mock_response.candidates = [MagicMock()]
            mock_response.candidates[0].content.parts = [MagicMock(text="Analyzing events...", thought=True)]
            
            mock_ai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            self.log_step(t_name, 1, "Gemini API successfully mocked with dark mafia story.")

            # Step 2: Call generate_story
            result = await generate_story(self.game_state, [], [])
            
            self.log_step(t_name, 2, f"MAJOR OUTPUT (Final Generated Post):\n{result}")

            self.assertIsNotNone(result)
            self.assertIn("The shadows of the mafia", result)
            
            self.log_result(t_name, True)
        except Exception as e:
            self.log_result(t_name, False, str(e))
            raise

if __name__ == '__main__':
    test_log.info("\n" + "="*60 + "\n   MAFIA BOT UNIT TEST SESSION: GAME & AI LOGIC\n" + "="*60)
    unittest.main()