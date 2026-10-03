# cogs/info.py
import logging
import discord
from discord import app_commands
from discord.ext import commands

from cogs.infocogs.mafiarules import show_rules_command
from cogs.infocogs.mafiaroles import show_roles_command
from cogs.infocogs.mafiainfo import show_info_command

logger = logging.getLogger('discord')


class InfoCog(commands.Cog, name="InfoCog"):
    """
    Handles general informational commands: rules, roles in current game,
    and bot command help list.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_game_instance(self):
        return getattr(self.bot, 'game_instance', None)

    @app_commands.command(name="mafiarules", description="Displays the main rules of the game.")
    async def show_rules(self, interaction: discord.Interaction):
        await show_rules_command(self, interaction)

    @app_commands.command(name="mafiaroles", description="Shows the roles and alignments in the current game.")
    async def show_roles(self, interaction: discord.Interaction):
        await show_roles_command(self, interaction)

    @app_commands.command(name="mafiainfo", description="Shows the list of available commands.")
    async def show_info(self, interaction: discord.Interaction):
        await show_info_command(self, interaction)


async def setup(bot: commands.Bot):
    """The setup function required by discord.py to load the cog."""
    await bot.add_cog(InfoCog(bot))
    logger.info("InfoCog loaded.")

