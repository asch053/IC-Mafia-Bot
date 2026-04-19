import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_0_logging import setup_test_logging
logger = setup_test_logging()

from cogs.stats import StatsCog

class TestStatsCog(unittest.IsolatedAsyncioTestCase):
    logger.info(f"--- Starting Test Suite: {__name__} ---")
    async def asyncSetUp(self):
        self.mock_bot = MagicMock()
        self.stats_cog = StatsCog(self.mock_bot)

    async def test_gamestats_command_success(self):
        msg = f"[START] {self._testMethodName} - Testing /gamestats response"
        print(f"\n{msg}"); logger.info(msg)
        
        with patch('cogs.stats.StatsCog._load_and_group_games') as mock_load_games:
            mock_load_games.return_value = {
                'classic': [{
                    'game_summary': {'winning_faction': 'Town', 'game_type': 'Classic'},
                    'player_data': [{'player_name': 'User1', 'is_winner': True, 'alignment': 'Town', 'role': 'Townie'}]
                }]
            }
            
            interaction = MagicMock()
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()
            
            action_msg = "[ACTION] Executing game_stats callback"
            print(action_msg); logger.info(action_msg)
            
            await self.stats_cog.game_stats.callback(self.stats_cog, interaction)
            
            args, kwargs = interaction.followup.send.call_args
            embed = kwargs.get('embed') or args[0]
            self.assertIn("Mafia Game Statistics", embed.title)
            
            outcome_msg = "[OUTCOME] Success! Valid stats embed generated and sent."
            print(outcome_msg); logger.info(outcome_msg)