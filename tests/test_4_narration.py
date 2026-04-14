import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_0_logging import setup_test_logging
logger = setup_test_logging()

from game.narration import NarrationManager

class TestNarrationManager(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_game = MagicMock()
        self.mock_game.game_settings = {"narration_type": "creative"}
        self.narration_manager = NarrationManager(self.mock_game)
        
        # Dummy players for events
        self.p1 = MagicMock()
        self.p1.display_name = "Alice"
        
        self.p2 = MagicMock()
        self.p2.display_name = "Bob"

    def test_add_event_queues_correctly(self):
        msg = f"[START] {self._testMethodName} - Testing that add_event queues data"
        print(f"\n{msg}"); logger.info(msg)
        
        action_msg = "[ACTION] Adding multiple events (kill, heal) to NarrationManager..."
        print(action_msg); logger.info(action_msg)
        
        self.narration_manager.add_event('kill', killer=self.p1, victim=self.p2)
        self.narration_manager.add_event('heal', doctor=self.p2, target=self.p1)
        
        self.assertEqual(len(self.narration_manager.events), 2)
        self.assertEqual(self.narration_manager.events[0]['type'], 'kill')
        self.assertEqual(self.narration_manager.events[0]['data']['killer'], self.p1)
        self.assertEqual(self.narration_manager.events[1]['type'], 'heal')
        
        outcome_msg = "[OUTCOME] Success! Events successfully stored in the queue with correct data attached."
        print(outcome_msg); logger.info(outcome_msg)

    @patch('game.narration.generate_ai_story')
    async def test_generate_story_uses_events(self, mock_generate_ai_story):
        msg = f"[START] {self._testMethodName} - Testing story generation from queued events"
        print(f"\n{msg}"); logger.info(msg)
        
        action_msg = "[ACTION] Pre-filling event queue and calling generate_story('night')..."
        print(action_msg); logger.info(action_msg)
        
        # Setup: Pre-fill the event queue with specific actions
        self.narration_manager.add_event('kill', killer=self.p1, victim=self.p2)
        self.narration_manager.add_event('kill_immune', killer=self.p2, victim=self.p1)
        
        # Mock the AI return string
        mock_generate_ai_story.return_value = "The night was dark and full of terrors."
        
        # Trigger the story generation
        story = await self.narration_manager.generate_story('night')
        
        # 1. Verify the AI was called
        mock_generate_ai_story.assert_called_once()
        
        # 2. Verify the prompt sent to the AI contained the events and player names
        prompt_passed_to_ai = mock_generate_ai_story.call_args[0][0]
        self.assertIn("Alice", prompt_passed_to_ai, "Prompt should contain killer's name (Alice)")
        self.assertIn("Bob", prompt_passed_to_ai, "Prompt should contain victim's name (Bob)")
        self.assertIn("kill", prompt_passed_to_ai.lower(), "Prompt should mention the kill event")
        
        # 3. Verify the returned story matches the AI output
        self.assertEqual(story, "The night was dark and full of terrors.")

        # 4. Verify the queue was cleared afterwards
        self.assertEqual(len(self.narration_manager.events), 0, "Event queue should be empty after generation")
        
        outcome_msg = "[OUTCOME] Success! Events compiled into prompt, AI successfully called, and queue cleared."
        print(outcome_msg); logger.info(outcome_msg)

    @patch('game.narration.generate_ai_story')
    async def test_generate_story_empty_events(self, mock_generate_ai_story):
        msg = f"[START] {self._testMethodName} - Testing story generation with NO events"
        print(f"\n{msg}"); logger.info(msg)
        
        action_msg = "[ACTION] Calling generate_story('day') with an empty event queue..."
        print(action_msg); logger.info(action_msg)
        
        # Ensure queue is completely empty
        self.narration_manager.events = []
        
        # Mock the AI return    
        mock_generate_ai_story.return_value = "It was a peaceful day. Nothing happened."
        
        # Trigger the story generation
        story = await self.narration_manager.generate_story('day')
        
        # Verify the AI was called despite the empty queue
        mock_generate_ai_story.assert_called_once()
        
        # Verify it handled it correctly and returned the story
        self.assertEqual(len(self.narration_manager.events), 0)
        self.assertEqual(story, "It was a peaceful day. Nothing happened.")
        
        outcome_msg = "[OUTCOME] Success! Empty events handled correctly and AI generated a peaceful story."
        print(outcome_msg); logger.info(outcome_msg)