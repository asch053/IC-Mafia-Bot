# cogs/community.py
import os
import logging
import discord
from discord.ext import commands
from discord import app_commands
import config

from cogs.communitycogs.setquirk import handle_set_quirk
from cogs.communitycogs.reviewquirks import handle_review_quirks
from cogs.communitycogs.displayquirks import handle_display_quirks

logger = logging.getLogger('discord')


class Community(commands.Cog):
    """Cog for community interaction and AI personalization."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cached_admin_id = self._resolve_admin_id()

    def _resolve_admin_id(self):
        """Attempts to find the MOD_CHANNEL_ID from config, bot, or env."""
        val = getattr(config, 'MOD_CHANNEL_ID', 0)
        if val == 0:
            val = getattr(self.bot, 'MOD_CHANNEL_ID', getattr(self.bot, 'ADMIN_CHANNEL_ID', 0))
        if val == 0:
            env_val = os.getenv('MOD_CHANNEL_ID')
            if env_val:
                try:
                    val = int(env_val)
                except ValueError:
                    val = 0
        return val

    @property
    def admin_review_channel_id(self):
        if self._cached_admin_id == 0:
            self._cached_admin_id = self._resolve_admin_id()
        return self._cached_admin_id

    @app_commands.command(name="set_quirk", description="Suggest a personality quirk for the AI narration")
    async def set_quirk(self, interaction: discord.Interaction):
        """Opens a modal, showing the user's current quirk if they have one."""
        await handle_set_quirk(self, interaction)

    @app_commands.command(name="review_quirks", description="[Admin Only] Review pending quirks")
    @app_commands.checks.has_permissions(administrator=True)
    async def review_quirks(self, interaction: discord.Interaction):
        """Loops through all pending quirks and provides approval buttons."""
        await handle_review_quirks(self, interaction)

    @app_commands.command(name="display_all_quirks", description="[Admin Only] List all approved player quirks")
    @app_commands.checks.has_permissions(administrator=True)
    async def display_all_quirks(self, interaction: discord.Interaction):
        """Displays all currently approved quirks in a batched list."""
        await handle_display_quirks(self, interaction)

    @review_quirks.error
    @display_all_quirks.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Only big boss admins can use this! ❌", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Community(bot))

