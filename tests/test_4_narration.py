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
    logger.info(f"--- Starting Test Suite: {__name__} ---")
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

    def test_mechanical_summary_block_and_block_missed(self):
        """Verifies that block events describe blocked actions and block_missed emits nothing."""
        from game.narration_ai import _generate_mechanical_summary
        
        target = MagicMock()
        target.role.name = "Godfather"
        target.role.abilities = ["kill"]
        target.display_name = "TargetBob"
        blocker = MagicMock()
        blocker.display_name = "BlockerAlice"
        
        # Test block_missed in classic (emits no lines)
        events = [{'type': 'block_missed', 'blocker': blocker, 'target': target}]
        summary = _generate_mechanical_summary(events)
        self.assertEqual(summary, "")

        # Test block on kill in classic: describes thwarted murder, hides identities
        events_kill = [{'type': 'block', 'blocker': blocker, 'target': target, 'action_type': 'kill'}]
        summary_kill = _generate_mechanical_summary(events_kill)
        self.assertIn("An attempted murder in the night was thwarted", summary_kill)
        self.assertNotIn("TargetBob", summary_kill)
        self.assertNotIn("Godfather", summary_kill)
        self.assertNotIn("BlockerAlice", summary_kill)

        # Test block on heal in classic
        events_heal = [{'type': 'block', 'blocker': blocker, 'target': target, 'action_type': 'heal'}]
        summary_heal = _generate_mechanical_summary(events_heal)
        self.assertIn("medical protection was intercepted", summary_heal)
        self.assertNotIn("TargetBob", summary_heal)

        # Test block on block in classic
        events_block = [{'type': 'block', 'blocker': blocker, 'target': target, 'action_type': 'block'}]
        summary_block = _generate_mechanical_summary(events_block)
        self.assertIn("attempt to interfere with another citizen was thwarted", summary_block)
        self.assertNotIn("TargetBob", summary_block)

        # Test block on investigate in classic: NEVER shown
        events_investigate = [{'type': 'block', 'blocker': blocker, 'target': target, 'action_type': 'investigate'}]
        summary_investigate = _generate_mechanical_summary(events_investigate)
        self.assertEqual(summary_investigate, "")

        # Test block in battle royale: identifies blocker and target
        events_br = [{'type': 'block_battle_royale', 'blocker': blocker, 'target': target, 'action_type': 'kill'}]
        summary_br = _generate_mechanical_summary(events_br)
        self.assertIn("BlockerAlice", summary_br)
        self.assertIn("TargetBob", summary_br)
        self.assertIn("attack", summary_br)

    def test_static_game_over_draw_and_winners(self):
        """Verifies static narration properly declares Draw and specific winners."""
        from game.narration_static import _generate_static_story_part

        draw_event = {'type': 'game_over', 'winner': 'Draw'}
        draw_text = _generate_static_story_part(draw_event, 'Classic Mafia')
        self.assertIn("DRAW", draw_text)
        self.assertIn("No one wins", draw_text)

        draw_event_lower = {'type': 'game_over', 'winner': 'draw'}
        draw_text_lower = _generate_static_story_part(draw_event_lower, 'Classic Mafia')
        self.assertIn("DRAW", draw_text_lower)

        town_event = {'type': 'game_over', 'winner': 'Town'}
        town_text = _generate_static_story_part(town_event, 'Classic Mafia')
        self.assertIn("The Town has WON the game", town_text)

        mafia_event = {'type': 'game_over', 'winner': 'Mafia'}
        mafia_text = _generate_static_story_part(mafia_event, 'Classic Mafia')
        self.assertIn("The Mafia has WON the game", mafia_text)

    def test_ai_game_over_directives(self):
        """Verifies that _construct_ai_prompt injects mandatory win-condition directives."""
        from game.narration_ai import _construct_ai_prompt

        draw_state = {
            'phase': 'Conclusion',
            'number': None,
            'story_type': 'Classic Mafia',
            'game_type': 'classic',
            'is_game_over': True,
            'winner': 'Draw',
            'living_players': []
        }
        draw_prompt = _construct_ai_prompt(draw_state, [], [])
        self.assertIn("CRITICAL: The conclusion narrative MUST explicitly declare that the conflict ended in a DRAW", draw_prompt)

        town_state = {
            'phase': 'Conclusion',
            'number': None,
            'story_type': 'Classic Mafia',
            'game_type': 'classic',
            'is_game_over': True,
            'winner': 'Town',
            'living_players': []
        }
        town_prompt = _construct_ai_prompt(town_state, [], [])
        self.assertIn("CRITICAL: The conclusion narrative MUST explicitly announce that the TOWN has WON the game", town_prompt)

    def test_kill_immune_anonymity_in_mechanical_summary_and_static(self):
        """Verifies that in Classic Mafia, immune targets are named by role and not player name."""
        from game.narration_ai import _generate_mechanical_summary
        from game.narration_static import _generate_static_story_part

        victim = MagicMock()
        victim.display_name = "PandaPlayer"
        victim.role.name = "Serial Killer"
        victim.role.display_name = "Serial Killer"

        event = {'type': 'kill_immune', 'victim': victim}

        # Classic mode: names the role, never the player name
        classic_summary = _generate_mechanical_summary([event], {'game_type': 'classic'})
        self.assertIn("Serial Killer", classic_summary)
        self.assertNotIn("PandaPlayer", classic_summary)
        self.assertIn("- 🛡️", classic_summary)

        # Battle Royale mode: names the player
        br_summary = _generate_mechanical_summary([event], {'game_type': 'battle_royale'})
        self.assertIn("PandaPlayer", br_summary)
        self.assertIn("- 🛡️", br_summary)

        # Static fallback stories: names role, does not leak player name
        romcom_text = _generate_static_story_part(event, 'Rom Com')
        self.assertIn("Serial Killer", romcom_text)
        self.assertNotIn("PandaPlayer", romcom_text)

        office_text = _generate_static_story_part(event, 'Office Restructuring')
        self.assertIn("Serial Killer", office_text)
        self.assertNotIn("PandaPlayer", office_text)

        classic_text = _generate_static_story_part(event, 'Classic Mafia')
        self.assertIn("Serial Killer", classic_text)
        self.assertNotIn("PandaPlayer", classic_text)

    def test_rules_block_in_prompt_and_random_bystanders(self):
        """Verifies rules_block is embedded in prompt and instructs random bystander inclusion with strict anonymity."""
        from game.narration_ai import _construct_ai_prompt

        state = {
            'phase': 'night',
            'number': 1,
            'story_type': 'Classic Mafia',
            'game_type': 'classic',
            'living_players': ['Panda', 'You_Fool', 'Soul'],
            'is_introduction': False,
            'is_game_over': False,
            'is_prologue': False
        }
        prompt = _construct_ai_prompt(state, [], [])
        self.assertIn("--- IRONCLAD RULES OF ANONYMITY (CLASSIC MAFIA) ---", prompt)
        self.assertIn("RANDOM CAMEO & BYSTANDER STORIES", prompt)
        self.assertIn("No reader should ever be able to glean any secret information", prompt)

    def test_random_living_players_in_classic_quirks(self):
        """Verifies that in Classic Mafia, living players are randomly sampled for cameos without role bias."""
        from game.narration_ai import _get_involved_quirks

        p1 = MagicMock(id=1, display_name="Alice", is_alive=True)
        p2 = MagicMock(id=2, display_name="Bob", is_alive=True)
        p3 = MagicMock(id=3, display_name="Charlie", is_alive=True)
        state = {
            'game_type': 'classic',
            'living_players': [p1, p2, p3],
            'is_introduction': False,
            'is_game_over': False,
            'is_prologue': False
        }
        with patch('community.quirk_logic.get_all_approved', return_value={'1': 'Loves apples', '2': 'Hates bananas', '3': 'Collects coins'}):
            with patch('random.sample', return_value=[p2]):
                quirks = _get_involved_quirks(state, [])
                self.assertIn("Bob", quirks)
                self.assertNotIn("Alice", quirks)
                self.assertNotIn("Charlie", quirks)