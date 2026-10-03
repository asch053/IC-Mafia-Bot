# cogs/export.py
import logging
import discord
from discord.ext import commands
from discord import app_commands

from cogs.exportcogs.sheets_client import get_sheets_client, connect_to_sheet
from cogs.exportcogs.compiler import compile_standard_data, compile_analytics_data
from cogs.exportcogs.exportstats import run_export_logic, handle_export_stats

logger = logging.getLogger('discord')


class ExportCog(commands.Cog):
    """Cog for exporting game history and player statistics to Google Sheets."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        self.creds, self.client = get_sheets_client()

    def _connect_to_sheet(self):
        return connect_to_sheet(self.creds, self.client)

    def _compile_standard_data(self, games):
        return compile_standard_data(games)

    def _compile_analytics_data(self, classic_games, stats_cog):
        return compile_analytics_data(classic_games, stats_cog)

    async def run_export_logic(self, channel: discord.TextChannel = None, game_mode: str = None):
        return await run_export_logic(self, channel, game_mode)

    @app_commands.command(name="exportstats", description="Force update the Google Sheet.")
    async def exportstats(self, interaction: discord.Interaction):
        await handle_export_stats(self, interaction)


async def setup(bot: commands.Bot):
    await bot.add_cog(ExportCog(bot))
    logger.info("ExportCog loaded.")

