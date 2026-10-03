# cogs/stats.py
import logging
import discord
from discord import app_commands
from discord.ext import commands

from cogs.statscogs import loaders, calculators, skillscore_calc
from cogs.statscogs.gamestats import handle_game_stats
from cogs.statscogs.playerstats import handle_player_stats
from cogs.statscogs.skillscore import handle_skill_score
from cogs.statscogs.leaderboard import handle_leaderboard
from cogs.statscogs.hallofrecords import handle_records

logger = logging.getLogger('discord')


class StatsCog(commands.Cog):
    """Cog for viewing player, game, leaderboard, and hall-of-records statistics."""

    def __init__(self, bot: commands.Bot):
        logger.info("Initializing StatsCog...")
        self.bot = bot

    async def player_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        choices = []
        if not interaction.guild:
            return []
        for member in interaction.guild.members:
            if current.lower() in member.display_name.lower() and not member.bot:
                choices.append(app_commands.Choice(name=member.display_name, value=str(member.id)))
        return choices[:25]

    def _load_game_file(self, file_path: str):
        return loaders.load_game_file(file_path)

    def _load_and_group_games(self) -> dict:
        return loaders.load_and_group_games()

    def _get_player_games(self, games_by_mode: dict, player_id: int) -> dict:
        return loaders.get_player_games(games_by_mode, player_id)

    def _calculate_win_rates(self, games: list, mode: str) -> dict:
        return calculators.calculate_win_rates(games, mode)

    def _calculate_player_stats(self, games: list, mode: str) -> dict:
        return calculators.calculate_player_stats(games, mode)

    def _calculate_battle_royale_player_stats(self, games: list, player_id: int) -> dict:
        return calculators.calculate_battle_royale_player_stats(games, player_id)

    def _calculate_classic_player_stats(self, games: list, player_id: int) -> dict:
        return calculators.calculate_classic_player_stats(games, player_id)

    def _build_player_stats_embed(self, member: discord.Member, player_games_by_mode: dict):
        return calculators.build_player_stats_embed(member, player_games_by_mode)

    def _phase_str_to_int(self, phase_str: str) -> int:
        return skillscore_calc.phase_str_to_int(phase_str)

    def _get_total_phases(self, player_list: list) -> int:
        return skillscore_calc.get_total_phases(player_list)

    def _get_lynched_player_for_phase(self, player_list: list, phase_str: str):
        return skillscore_calc.get_lynched_player_for_phase(player_list, phase_str)

    def _calculate_skill_scores(self, member_id: int, games: list) -> dict:
        return skillscore_calc.calculate_skill_scores(member_id, games)

    @app_commands.command(name="gamestats", description="Displays overall statistics from past games.")
    async def game_stats(self, interaction: discord.Interaction):
        """Calculates and displays overall game and player statistics."""
        await handle_game_stats(self, interaction)

    @app_commands.command(name="playerstats", description="Displays detailed statistics for a specific player.")
    @app_commands.describe(player="The server member you want to look up.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def playerstats(self, interaction: discord.Interaction, player: str):
        await handle_player_stats(self, interaction, player)

    @app_commands.command(name="skillscore", description="Calculates a player's skill score for Classic mode.")
    @app_commands.describe(member="The player to look up (defaults to yourself).")
    async def skillscore(self, interaction: discord.Interaction, member: discord.User = None):
        await handle_skill_score(self, interaction, member)

    @app_commands.command(name="leaderboard", description="View the top 10 players by various metrics.")
    @app_commands.choices(metric=[
        app_commands.Choice(name="Skill Score (Overall)", value="skill"),
        app_commands.Choice(name="Greatest Survivor (Highest Life Rate)", value="survivor"),
        app_commands.Choice(name="Red Shirt (Most Likely to Die)", value="red_shirt")
    ])
    async def leaderboard(self, interaction: discord.Interaction, metric: str):
        await handle_leaderboard(self, interaction, metric)

    @app_commands.command(name="hall_of_records", description="View the Mafia records (Classic only).")
    @app_commands.describe(days="Filter stats to only include games from the last X days (Leave blank for All-Time).")
    async def records(self, interaction: discord.Interaction, days: int = None):
        await handle_records(self, interaction, days)


async def setup(bot: commands.Bot):
    """The setup function required by discord.py to load the cog."""
    await bot.add_cog(StatsCog(bot))

