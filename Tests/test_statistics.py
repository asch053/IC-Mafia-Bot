import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from Cogs.stats import StatsCog
import discord

class TestStatsCog(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.mock_bot = MagicMock()
        self.stats_cog = StatsCog(self.mock_bot)

    async def test_gamestats_command_success(self):
        with patch('Cogs.stats.StatsCog._load_and_group_games') as mock_load_games:
            mock_load_games.return_value = {
                'classic': [{
                    'game_summary': {'winning_faction': 'Town', 'game_type': 'Classic'},
                    'player_data': [
                        {'player_name': 'User1', 'is_winner': True, 'alignment': 'Town', 'role': 'Townie'}
                    ]
                }]
            }
            
            interaction = MagicMock()
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()
            
            await self.stats_cog.game_stats.callback(self.stats_cog, interaction)
            
            args, kwargs = interaction.followup.send.call_args
            embed = kwargs.get('embed') or args[0]
            self.assertIn("Mafia Game Statistics", embed.title)

    async def test_gamestats_no_data(self):
        with patch('Cogs.stats.StatsCog._load_and_group_games') as mock_load:
            mock_load.return_value = {} 
            interaction = MagicMock()
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()
            
            await self.stats_cog.game_stats.callback(self.stats_cog, interaction)
            
            args, kwargs = interaction.followup.send.call_args
            self.assertIn("No game data found", args[0] if args else kwargs.get('content'))

    async def test_playerstats_command(self):
        with patch('Cogs.stats.StatsCog._load_and_group_games') as mock_load:
            mock_load.return_value = {'classic': [{'game_summary': {'game_type': 'Classic'}, 'player_data': [{'player_id': 123, 'player_name': 'Hero', 'is_winner': True}]}]}
            
            interaction = MagicMock()
            interaction.guild.fetch_member = AsyncMock()
            mock_member = MagicMock(id=123, display_name="Hero")
            mock_member.display_avatar.url = "url"
            interaction.guild.fetch_member.return_value = mock_member
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()

            await self.stats_cog.playerstats.callback(self.stats_cog, interaction, "123")
            args, kwargs = interaction.followup.send.call_args
            self.assertIn("Hero", (kwargs.get('embed') or args[0]).title)

    async def test_skillscore_calculation(self):
        with patch('Cogs.stats.config') as mock_config, \
             patch('Cogs.stats.StatsCog._load_and_group_games') as mock_load_games:
            
            # Config
            mock_config.SKILL_WEIGHT_PERSUASION = 1
            mock_config.SKILL_WEIGHT_ELUSIVENESS = 1
            mock_config.SKILL_WEIGHT_UNDERSTANDING = 1
            mock_config.SKILL_WIN_WEIGHT_TOWN = 0.55
            mock_config.SKILL_WIN_WEIGHT_MAFIA = 0.35
            mock_config.SKILL_WIN_WEIGHT_NEUTRAL = 0.10
            mock_config.SKILL_EARLY_GAME_PERCENT = 0.25

            # Ensure mock data structure is perfect
            mock_load_games.return_value = {
                'classic': [{
                    'game_summary': {'game_type': 'Classic'},
                    'player_data': [
                        {
                            'player_id': 123, 
                            'player_name': 'SkilledPlayer',
                            'is_winner': True, 
                            'alignment': 'Town', 
                            'death_phase': None, 
                            'death_cause': None
                        },
                    ],
                    'lynch_vote_history': []
                }]
            }

            interaction = MagicMock()
            interaction.user.id = 123
            interaction.user.display_name = "SkilledPlayer"
            interaction.user.display_avatar.url = "url"
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()

            await self.stats_cog.skillscore.callback(self.stats_cog, interaction)

            args, kwargs = interaction.followup.send.call_args
            content = args[0] if args else kwargs.get('embed')
            
            if isinstance(content, str):
                 self.fail(f"Skillscore failed with message: {content}")
                 
            embed = content
            self.assertIn("Score", embed.fields[0].name)

if __name__ == '__main__':
    unittest.main()