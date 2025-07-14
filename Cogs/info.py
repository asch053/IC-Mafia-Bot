# Cogs/info.py
import discord
from discord import app_commands
from discord.ext import commands
import logging
from collections import Counter
from utils.utilities import load_data

logger = logging.getLogger('discord')

class InfoCog(commands.Cog, name="InfoCog"):
    """Cog for general informational commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_game_instance(self):
        """Helper to safely get the game instance from GameCog."""
        game_cog = self.bot.get_cog('GameCog')
        return game_cog.game if game_cog else None

    @app_commands.command(name="mafiarules", description="Displays the main rules of the game.")
    async def show_rules(self, interaction: discord.Interaction):
        try:
            rules_text = "\n".join(load_data("data/rules.txt"))
            embed = discord.Embed(title="📜 Mafia Game Rules", description=rules_text, color=discord.Color.blue())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            await interaction.response.send_message("Sorry, I couldn't load the rules file.", ephemeral=True)

    @app_commands.command(name="mafiaroles", description="Shows the roles and alignments in the current game.")
    async def show_roles(self, interaction: discord.Interaction):
        game = self.get_game_instance()
        if not game or not game.game_roles:
            await interaction.response.send_message("No game is running or roles have not been assigned yet.", ephemeral=True)
            return

        # Count the occurrences of each role name
        role_counts = Counter(role.name for role in game.game_roles)
        
        # Group roles by alignment
        roles_by_alignment = {"Town": [], "Mafia": [], "Neutral": []}
        for role_name, count in role_counts.items():
            # Find a sample role object to get its alignment
            sample_role = next((r for r in game.game_roles if r.name == role_name), None)
            if sample_role:
                alignment = sample_role.alignment
                role_str = f"{role_name} ({count})" if count > 1 else role_name
                if alignment in roles_by_alignment:
                    roles_by_alignment[alignment].append(role_str)

        embed = discord.Embed(
            title=f"Roles for Game #{game.game_settings['game_id']}",
            description=f"There are **{len(game.players)}** players in this game.",
            color=discord.Color.dark_teal()
        )

        for alignment, roles in roles_by_alignment.items():
            if roles:
                embed.add_field(name=f"--- {alignment} ---", value="\n".join(sorted(roles)), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="mafiainfo", description="Shows the list of available commands.")
    async def show_info(self, interaction: discord.Interaction):
        embed = discord.Embed(title="ℹ️ Mafia Bot Commands", color=discord.Color.green())
        
        player_commands = (
            "`/mafiajoin` - Join the game during sign-ups.\n"
            "`/mafialeave` - Leave the game during sign-ups.\n"
            "`/mafiastatus` - See the current game status.\n"
            "`/vote [player]` - Vote to lynch a player.\n"
            "`/votecount` - See the current vote tally.\n"
            "`/mafiarules` - Read the game rules.\n"
            "`/mafiaroles` - See roles in the current game."
        )
        embed.add_field(name="Player Commands", value=player_commands, inline=False)
        
        action_commands = (
            "`/kill [player]` - (DM Only) Target a player to kill at night.\n"
            "`/heal [player]` - (DM Only) Target a player to protect at night.\n"
            "`/investigate [player]` - (DM Only) Target a player to investigate.\n"
            "`/block [player]` - (DM Only) Target a player to block at night."
        )
        embed.add_field(name="Night Actions", value=action_commands, inline=False)

        admin_commands = (
            "`/mafiastart` - Schedule a new game.\n"
            "`/mafiastop` - Forcibly end the current game.\n"
            "`/forcestart` - End sign-ups and start the game now."
        )
        embed.add_field(name="Admin Commands", value=admin_commands, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(InfoCog(bot))