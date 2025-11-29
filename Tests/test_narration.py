import unittest
from unittest.mock import MagicMock
from game.narration import NarrationManager

class TestNarrationManager(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # FIX: No arguments for the non-AI branch version
        self.manager = NarrationManager()

    def create_mock_player(self, name):
        p = MagicMock()
        p.display_name = name
        p.role = MagicMock()
        p.role.name = "Townie"
        p.role.alignment = "Town"
        return p

    async def test_lifecycle_add_construct_clear(self):
        if hasattr(self.manager, 'current_phase_events'):
            self.assertEqual(len(self.manager.current_phase_events), 0)

        self.manager.add_event('no_lynch')
        
        # NO await here, function is sync
        story = self.manager.construct_story("Day", 1)
        self.assertIn("Day 1", story)
        self.assertIn("no one was lynched", story) 

        self.manager.clear()
        if hasattr(self.manager, 'current_phase_events'):
            self.assertEqual(len(self.manager.current_phase_events), 0)
            
        empty_story = self.manager.construct_story("Night", 1)
        # FIX: Expect None because we cleared the events
        self.assertIsNone(empty_story)

    async def test_story_lynch(self):
        victim = self.create_mock_player("Alice")
        self.manager.add_event('lynch', victims=[victim])
        
        story = self.manager.construct_story("Day", 2)
        
        self.assertIn("Alice", story)
        self.assertIn("strung up", story)

    async def test_story_kill(self):
        killer = self.create_mock_player("Bob")
        victim = self.create_mock_player("Charlie")
        self.manager.add_event('kill', killer=killer, victim=victim)
        
        story = self.manager.construct_story("Night", 2)
        
        self.assertIn("Charlie", story)
        self.assertIn("body of", story)

    async def test_story_save(self):
        healer = self.create_mock_player("Dr. Dan")
        victim = self.create_mock_player("Eric")
        self.manager.add_event('save', healer=healer, victim=victim)
        
        story = self.manager.construct_story("Night", 2)
        
        self.assertIn("Eric", story)
        self.assertIn("saved", story)

    async def test_story_game_over(self):
        winner_name = "The Town"
        self.manager.add_event('game_over', winner=winner_name)
        
        story = self.manager.construct_story("Day", 5)
        
        self.assertIn("game is over", story) 
        self.assertIn("The Town", story)

    async def test_fallback_behavior(self):
        self.manager.add_event('alien_invasion', details="All humans died")
        try:
            story = self.manager.construct_story("Day", 99)
            self.assertIsInstance(story, str)
            self.assertIn("mysterious event", story) 
        except Exception as e:
            self.fail(f"Narrator crashed: {e}")

if __name__ == '__main__':
    unittest.main()