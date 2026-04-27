import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import logging

# Ensure root directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 1. Initialize Logging
from tests.test_0_logging import setup_test_logging
logger = setup_test_logging()

# 2. Imports for components under test
from game.player import Player
from game.narration import NarrationManager
from game.roles import get_role_instance, ROLE_CLASSES
from game.narration_ai import (
    _construct_ai_prompt, 
    _generate_mechanical_summary, 
    _get_involved_quirks,
    generate_story
)

class TestNarrationManager(unittest.IsolatedAsyncioTestCase):
    """
    Checks that stories are correctly formatted and generated from queued narration events,
    with special focus on Fog of War / Privacy logic between Classic and Battle Royale.
    """
    
    def setUp(self):
        """Standard environment setup for narration tests."""
        self.narration_manager = NarrationManager()
        
        # We use real Player objects to ensure 'id' vs 'user_id' logic is correctly tested
        self.p1 = Player(101, "Alice#0001", "Alice")
        self.p2 = Player(102, "Bob#0002", "Bob")
        
        # Assign dummy roles
        self.p1.role = get_role_instance("Town Cop")
        self.p2.role = get_role_instance("Mob Goon")
        
        # Mock the game_state dictionary
        self.game_state = {
            "game_id": "TEST_G_999",
            "phase": "night",
            "number": 1,
            "story_type": "classic",
            "game_type": "classic",
            "living_players": [self.p1, self.p2],
            "is_introduction": False,
            "is_game_over": False,
            "is_prologue": False
        }

    def log_step(self, step_num, description):
        msg = f"[{self._testMethodName}] STEP {step_num}: {description}"
        print(msg); logger.info(msg)

    def log_result(self, passed, reason=None):
        status = "PASSED ✅" if passed else f"FAILED ❌ (Reason: {reason})"
        msg = f"[{self._testMethodName}] RESULT: {status}"
        print(msg); logger.info(msg)

    # --- ROLE SYSTEM INTEGRITY ---

    def test_role_loading_integrity(self):
        """Tests that roles load correctly and map to the right Python classes."""
        t_name = "test_role_loading_integrity"
        self.log_step(0, "Starting Role Verification...")
        
        try:
            self.log_step(1, "Attempting to load 'Town Cop'...")
            cop = get_role_instance("Town Cop")
            self.assertIsNotNone(cop)
            # Verify class inheritance
            self.assertTrue(isinstance(cop, ROLE_CLASSES["TownInvestigative"]), "Town Cop is not a TownInvestigative instance")
            self.log_step(2, f"Verified class: {type(cop).__name__}")

            self.log_step(3, "Attempting to load 'Godfather'...")
            gf = get_role_instance("Godfather")
            self.assertEqual(gf.alignment, "Mafia")
            
            # FIX: Check for 'investigate_immune' OR 'investigation_immune'
            is_immune = getattr(gf, 'investigate_immune', getattr(gf, 'investigation_immune', False))
            self.assertTrue(is_immune, "Godfather failed to inherit any known immunity attributes")
            
            self.log_result(True)
        except Exception as e:
            self.log_result(False, str(e)); raise

    # --- FOG OF WAR & PRIVACY LOGIC TESTS ---

    def test_classic_fog_of_war_secrecy(self):
        """CHECK: In Classic mode, hidden actors and immune targets remain anonymous."""
        self.log_step(0, "Starting Fog of War Secrecy Test (Classic Mode)")
        try:
            self.game_state["game_type"] = "classic"
            
            # Scenario: Bob (Killer) attacks Alice (Target), but Alice survives
            events = [{'type': 'kill_failed', 'victim': self.p1, 'killer': self.p2}]
            
            self.log_step(1, "Constructing AI prompt for Classic save event.")
            prompt = _construct_ai_prompt(self.game_state, events, [])
            summary = _generate_mechanical_summary(self.game_state, events)

            # Verification: Prompt Secrecy
            mech_header = "--- MECHANICAL EVENTS TO NARRATE ---"
            self.assertIn(mech_header, prompt, "Prompt is missing mechanical section header")
            
            mechanical_section = prompt.split(mech_header)[1]
            self.assertNotIn("Alice", mechanical_section, "Target name 'Alice' leaked in Classic AI prompt (Mechanical Events section)")
            self.assertNotIn("Bob", mechanical_section, "Attacker name 'Bob' leaked in Classic AI prompt (Mechanical Events section)")
            self.assertIn("target survived anonymously", mechanical_section.lower())

            # Verification: Summary Secrecy
            self.assertNotIn("Alice", summary, "Target name leaked in Classic mechanical summary")
            self.assertIn("attempt on a life was thwarted", summary)
            
            self.log_step(2, f"Major Output (Summary): {summary}")
            self.log_result(True)
        except Exception as e:
            self.log_result(False, str(e)); raise

    @patch('community.quirk_logic.get_all_approved')
    def test_classic_quirk_privacy(self, mock_quirks):
        """CHECK: In Classic, only the victim's quirk is sent to AI, not the secret killer's."""
        self.log_step(0, "Starting Quirk Privacy Test (Classic)")
        try:
            self.game_state["game_type"] = "classic"
            
            # Mock quirks for Alice (101) and Bob (102)
            mock_quirks.return_value = {
                "101": "Loves knitting sweaters.", # Alice (Victim)
                "102": "Always talks in riddles."   # Bob (Killer)
            }
            
            # Event: Bob kills Alice
            events = [{'type': 'kill', 'victim': self.p1, 'killer': self.p2}]
            
            self.log_step(1, "Filtering involved quirks for a Classic kill.")
            quirks_output = _get_involved_quirks(self.game_state, events)
            
            # The victim's quirk should be included because the discovery is public
            self.assertIn("Alice", quirks_output, "Victim name 'Alice' should be in quirk block")
            self.assertIn("knitting", quirks_output, "Victim quirk content missing")
            
            # The killer's quirk MUST be excluded to prevent AI "outing" them
            self.assertNotIn("Bob", quirks_output, "Killer name 'Bob' leaked in Classic quirk block!")
            self.assertNotIn("riddles", quirks_output, "Killer quirk content leaked in Classic mode!")
            
            self.log_step(2, f"Major Output (Quirks Block):\n{quirks_output}")
            self.log_result(True)
        except Exception as e:
            self.log_result(False, str(e)); raise

    def test_battle_royale_transparency(self):
        """CHECK: In Battle Royale, attackers and targets are identified by name."""
        self.log_step(0, "Starting Battle Royale Transparency Test")
        try:
            self.game_state["game_type"] = "battle_royale"
            
            # Scenario: Alice kills Bob in BR
            events = [{'type': 'kill_battle_royale', 'victim': self.p2, 'killer': self.p1}]
            
            self.log_step(1, "Constructing AI prompt for Battle Royale kill.")
            prompt = _construct_ai_prompt(self.game_state, events, [])
            summary = _generate_mechanical_summary(self.game_state, events)

            # Verification: In BR, both names should be present
            self.assertIn("Alice", prompt, "Attacker 'Alice' missing from BR prompt")
            self.assertIn("Bob", prompt, "Victim 'Bob' missing from BR prompt")
            self.assertIn("eliminated by: Alice", summary, "Attacker name missing from BR summary")
            
            self.log_result(True)
        except Exception as e:
            self.log_result(False, str(e)); raise

if __name__ == '__main__':
    logger.info(f"--- Starting Test Suite: {__name__} ---")
    unittest.main()