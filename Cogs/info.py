# Cogs/info.py
import discord
from discord import app_commands
from discord.ext import commands
import logging
from collections import Counter, defaultdict
from utils.utilities import load_data

# Get the logger instance from the main bot file
logger = logging.getLogger('discord')

class InfoCog(commands.Cog, name="InfoCog"):
    """
    This cog handles all general informational commands that players can use,
    such as checking rules, viewing roles in the current game, and listing
    all available bot commands.
    """

    def __init__(self, bot: commands.Bot):
        """Initializes the InfoCog, keeping a reference to the bot."""
        self.bot = bot

    def get_game_instance(self):
        """
        A helper method to safely retrieve the active game instance from the GameCog.
        Returns the Game object if a game is running, otherwise returns None.
        """
        # Access the 'GameCog' instance that has been loaded into the bot
        game_cog = self.bot.get_cog('GameCog')
        # Return the 'game' attribute from the cog, which holds the game state
        return game_cog.game if game_cog else None

    @app_commands.command(name="mafiarules", description="Displays the main rules of the game.")
    async def show_rules(self, interaction: discord.Interaction):
        """Sends an ephemeral message to the user containing the game rules from rules.txt."""
        logger.info(f"'/mafiarules' command invoked by {interaction.user.name}.")
        try:
            # Load the rules text using our utility function
            rules_text = "\n".join(load_data("data/rules.txt"))
            # Create a nice-looking embed to display the rules
            embed = discord.Embed(title="📜 Mafia Game Rules", description=rules_text, color=discord.Color.blue())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Successfully sent rules to {interaction.user.name}.")
        except Exception as e:
            # Log an error if the rules file can't be loaded for some reason
            logger.error(f"Failed to load data/rules.txt for '/mafiarules' command.", exc_info=True)
            await interaction.response.send_message("Sorry, I couldn't load the rules file at the moment.", ephemeral=True)

    @app_commands.command(name="mafiaroles", description="Shows the roles and alignments in the current game.")
    async def show_roles(self, interaction: discord.Interaction):
        """Displays a public list of all roles in the game, grouped by alignment."""
        logger.info(f"'/mafiaroles' command invoked by {interaction.user.name}.")
        game = self.get_game_instance()

        # First, check if a game is running and roles have been set
        if not game or not game.game_roles:
            logger.warning(f"'/mafiaroles' command failed: No active game or roles not assigned.")
            await interaction.response.send_message("No game is running or roles have not been assigned yet.", ephemeral=True)
            return

        # Use a Counter to get the quantity of each role (e.g., "Plain Townie: 4")
        role_counts = Counter(role.name for role in game.game_roles)
        # Use a defaultdict to easily group roles by their alignment
        roles_by_alignment = defaultdict(list)
        
        # Iterate through the unique roles and their counts
        for role_name, count in role_counts.items():
            # Find a single instance of the role to check its alignment
            sample_role = next((r for r in game.game_roles if r.name == role_name), None)
            if sample_role:
                alignment = sample_role.alignment
                # Format the string to include the count if it's more than one
                role_str = f"{role_name} ({count})" if count > 1 else role_name
                roles_by_alignment[alignment].append(role_str)
        
        # Build the embed to display the role list
        embed = discord.Embed(
            title=f"Roles for Game #{game.game_settings.get('game_id', 'N/A')}",
            description=f"There are **{len(game.players)}** players in this game.",
            color=discord.Color.dark_teal()
        )
        
        # Sort the alignments alphabetically for a consistent order
        for alignment, roles in sorted(roles_by_alignment.items()):
            if roles:
                # Add a field for each alignment with its list of roles
                embed.add_field(name=f"--- {alignment} ---", value="\n".join(sorted(roles)), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Successfully sent role list to {interaction.user.name}.")

    @app_commands.command(name="mafiainfo", description="Shows the list of available commands.")
    async def show_info(self, interaction: discord.Interaction):
        """Displays a comprehensive and accurate list of all bot commands, grouped by category."""
        logger.info(f"'/mafiainfo' command invoked by {interaction.user.name}.")
        
        # Create the main embed for the help message
        embed = discord.Embed(title="ℹ️ Mafia Bot Commands", color=discord.Color.green())
        
        # Define the text block for general player commands
        player_commands = (
            "`/mafiajoin` - Join the game during sign-ups.\n"
            "`/mafialeave` - Leave the game during sign-ups.\n"
            "`/mafiastatus` - See the current game status.\n"
            "`/vote` - Vote to lynch a player during the day.\n"
            "`/mafiacount` - See the current vote tally.\n"
            "`/myrole` - (DM Only) Have your role resent to you.\n"
            "`/mafiarules` - Read the game rules.\n"
            "`/mafiaroles` - See roles in the current game.\n"
            "`/gamestats` - View statistics from all completed games.\n"
            "`/playerstats` - View any player's game statistics.\n"
        )
        embed.add_field(name="Player Commands", value=player_commands, inline=False)
        
        # Define the text block for secret night action commands
        action_commands = (
            "`/kill` - (DM Only) Target a player to kill at night.\n"
            "`/heal` - (DM Only) Target a player to protect at night.\n"
            "`/investigate` - (DM Only) Target a player to investigate.\n"
            "`/block` - (DM Only) Target a player to block at night."
        )
        embed.add_field(name="Night Actions", value=action_commands, inline=False)

        # Define the text block for administrator-only commands
        admin_commands = (
            "`/mafiastart` - Schedule a new game.\n"
            "`/mafiastop` - Forcibly end the current game.\n"
            "`/forcestart` - End sign-ups and start the game now.\n"
            "`/mafiareinit` - (Debug) Rebuild player list from roles."
        )
        embed.add_field(name="Admin Commands", value=admin_commands, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Successfully sent command list to {interaction.user.name}.")

async def setup(bot):
    """The setup function required by discord.py to load the cog."""
    await bot.add_cog(InfoCog(bot))

