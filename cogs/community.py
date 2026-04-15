import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
import config

from community.review_system import QuirkSubmissionModal, QuirkReviewView
from community import quirk_logic

logger = logging.getLogger('discord')

class Community(commands.Cog):
    """Cog for community interaction and AI personalization."""
    def __init__(self, bot):
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
                try: val = int(env_val)
                except ValueError: val = 0
        return val

    @property
    def admin_review_channel_id(self):
        if self._cached_admin_id == 0:
            self._cached_admin_id = self._resolve_admin_id()
        return self._cached_admin_id

    @app_commands.command(name="set_quirk", description="Suggest a personality quirk for the AI narration")
    async def set_quirk(self, interaction: discord.Interaction):
        """Opens a modal, showing the user's current quirk if they have one."""
        target_id = self.admin_review_channel_id
        if target_id == 0:
            return await interaction.response.send_message("Review channel not configured! 🛠️", ephemeral=True)
        
        current = quirk_logic.get_user_quirk(interaction.user.id)
        await interaction.response.send_modal(QuirkSubmissionModal(target_id, current_quirk=current))

    @app_commands.command(name="review_quirks", description="[Admin Only] Review pending quirks")
    @app_commands.checks.has_permissions(administrator=True)
    async def review_quirks(self, interaction: discord.Interaction):
        """Loops through all pending quirks and provides approval buttons."""
        pending = quirk_logic.get_all_pending()
        if not pending:
            return await interaction.response.send_message("The queue is empty, cutie! 💅", ephemeral=True)
        
        await interaction.response.send_message("Fetching pending items...", ephemeral=True)
        for user_id_str, quirk_text in pending.items():
            user_id = int(user_id_str)
            current_approved = quirk_logic.get_user_quirk(user_id)
            
            embed = discord.Embed(title="Reviewing Quirk", color=discord.Color.orange())
            embed.add_field(name="Player", value=f"<@{user_id}>", inline=False)
            
            if current_approved:
                embed.add_field(name="Currently Active", value=f"*{current_approved}*", inline=True)
                embed.add_field(name="Proposed Change", value=f"**{quirk_text}**", inline=True)
            else:
                embed.add_field(name="New Quirk", value=f"\"{quirk_text}\"", inline=False)
            
            await interaction.channel.send(embed=embed, view=QuirkReviewView(user_id))

    @app_commands.command(name="display_all_quirks", description="[Admin Only] List all approved player quirks")
    @app_commands.checks.has_permissions(administrator=True)
    async def display_all_quirks(self, interaction: discord.Interaction):
        """Displays all currently approved quirks in a batched list."""
        approved = quirk_logic.get_all_approved()
        if not approved:
            return await interaction.response.send_message("No approved quirks found! 🏜️", ephemeral=True)
            
        await interaction.response.send_message("Generating quirks list...", ephemeral=True)
        embed = discord.Embed(title="Approved Player Quirks", color=discord.Color.green())
        content = ""
        for uid, quirk in approved.items():
            line = f"<@{uid}>: {quirk}\n"
            if len(content) + len(line) > 3800:
                embed.description = content
                await interaction.followup.send(embed=embed, ephemeral=True)
                content, embed = line, discord.Embed(title="Approved Player Quirks (Cont.)", color=discord.Color.green())
            else: content += line
        if content:
            embed.description = content
            await interaction.followup.send(embed=embed, ephemeral=True)

    @review_quirks.error
    @display_all_quirks.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Only big boss admins can use this! ❌", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Community(bot))