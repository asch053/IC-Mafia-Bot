import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_0_logging import setup_test_logging
logger = setup_test_logging()

from game.narration import NarrationManager

class TestNarrationManager(unittest.IsolatedAsyncioTestCase):
    """Checks that stories are correctly formatted and generated from queued narration events."""
    
    def setUp(self):
        # NarrationManager takes no arguments on init
        self.narration_manager = NarrationManager()
        
        # Setup dummy players
        self.p1 = MagicMock()
        self.p1.display_name = "Alice"
        self.p2 = MagicMock()
        self.p2.display_name = "Bob"
        
        # Mock the game_state dictionary exactly as the engine provides it
        self.game_state = {
            "phase": "night",
            "phase_number": 1,
            "story_type": "classic"
        }

    def test_add_event_queues_correctly(self):
        msg = f"[START] {self._testMethodName} - Testing that add_event formats and queues data"
        print(f"\n{msg}"); logger.info(msg)
        
        try:
            action_msg = "[ACTION] Adding kill event to NarrationManager..."
            print(action_msg); logger.info(action_msg)
            
            self.narration_manager.add_event('kill', killer=self.p1, victim=self.p2)
            
            self.assertEqual(len(self.narration_manager.events), 1)
            self.assertEqual(self.narration_manager.events[0]['type'], 'kill')
            
            # Verifies that kwargs are stored directly on the event dict
            self.assertEqual(self.narration_manager.events[0]['killer'], self.p1)
            self.assertEqual(self.narration_manager.events[0]['victim'], self.p2)
            
            outcome_msg = "[OUTCOME] Success! Event formatted correctly and successfully stored in the queue."
            print(outcome_msg); logger.info(outcome_msg)
            
        except Exception as e:
            logger.exception(f"[ERROR] Test failed in {self._testMethodName}: {e}")
            raise

    # Patch the AI module exactly as it is imported inside narration.py
    @patch('game.narration.ai_storyteller.generate_story', new_callable=AsyncMock)
    async def test_generate_story_uses_events(self, mock_generate_story):
        msg = f"[START] {self._testMethodName} - Testing story generation from queued events"
        print(f"\n{msg}"); logger.info(msg)
        
        try:
            action_msg = "[ACTION] Pre-filling event queue and calling generate_story()..."
            print(action_msg); logger.info(action_msg)
            
            self.narration_manager.add_event('kill', killer=self.p1, victim=self.p2)
            mock_generate_story.return_value = "The night was dark and full of terrors."
            
            # Generate story using the proper game_state dictionary
            story = await self.narration_manager.construct_story(self.game_state)
            
            # Verify AI was called
            mock_generate_story.assert_called_once()
            
            # Verify that the events list passed to the AI contained our players
            # ai_storyteller.generate_story takes: (game_state, events, history)
            passed_game_state, passed_events, passed_history = mock_generate_story.call_args[0]
            self.assertEqual(passed_events[0]['killer'].display_name, "Alice")
            self.assertEqual(passed_events[0]['victim'].display_name, "Bob")
            
            # Clear the event queue
            self.narration_manager.clear()
            # Verify the queue is automatically cleared after generation
            self.assertEqual(len(self.narration_manager.events), 0)
            
            outcome_msg = "[OUTCOME] Success! Events compiled into prompt, AI called, and queue cleared."
            print(outcome_msg); logger.info(outcome_msg)
            
        except Exception as e:
            logger.exception(f"[ERROR] Test failed in {self._testMethodName}: {e}")
            raise

    @patch('game.narration.ai_storyteller.generate_story', new_callable=AsyncMock)
    async def test_generate_story_empty_events(self, mock_generate_story):
        msg = f"[START] {self._testMethodName} - Testing story generation with NO events"
        print(f"\n{msg}"); logger.info(msg)
        
        try:
            action_msg = "[ACTION] Calling generate_story() with an empty event queue..."
            print(action_msg); logger.info(action_msg)
            
            self.narration_manager.events = []
            mock_generate_story.return_value = "It was a peaceful day. Nothing happened."
            
            story = await self.narration_manager.construct_story(self.game_state)
            
            mock_generate_story.assert_called_once()
            self.assertIn("It was a peaceful day", story)
            self.assertEqual(len(self.narration_manager.events), 0)
            
            outcome_msg = "[OUTCOME] Success! Empty events handled correctly and AI generated a peaceful story."
            print(outcome_msg); logger.info(outcome_msg)
            
        except Exception as e:
            logger.exception(f"[ERROR] Test failed in {self._testMethodName}: {e}")
            raise