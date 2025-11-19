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

    # --- Command to show game rules ---
    @app_commands.command(name="mafiarules", description="Displays the main rules of the game.")
    async def show_rules(self, interaction: discord.Interaction):
        """Sends an ephemeral message to the user containing the game rules from rules.txt."""
        logger.info(f"'/mafiarules' command invoked by {interaction.user.name}.")
        try:
            # Load the rules text using our utility function
            rules_text = "\n".join(load_data("Data/rules.txt"))
            # Create a nice-looking embed to display the rules
            embed = discord.Embed(title="📜 Mafia Game Rules", description=rules_text, color=discord.Color.blue())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Successfully sent rules to {interaction.user.name}.")
        except Exception as e:
            # Log an error if the rules file can't be loaded for some reason
            logger.error(f"Failed to load Data/rules.txt for '/mafiarules' command.", exc_info=True)
            await interaction.response.send_message("Sorry, I couldn't load the rules file at the moment.", ephemeral=True)
    
    # --- Command to show roles in the current game ---
    @app_commands.command(name="mafiaroles", description="Shows the roles and alignments in the current game.")
    async def show_roles(self, interaction: discord.Interaction):
        """Displays a public list of all roles, including alive/total counts."""
        logger.info(f"'/mafiaroles' command invoked by {interaction.user.name}.")
        game = self.get_game_instance()
        # First, check if a game is running and roles have been set
        if not game or not game.game_roles:
            logger.warning(f"'/mafiaroles' command failed: No active game or roles not assigned.")
            await interaction.response.send_message("No game is running or roles have not been assigned yet.", ephemeral=True)
            return
        # --- Get total and alive counts for each role ---
        # 1. Get TOTAL counts of each role (e.g., "Townie: 5")
        total_role_counts = Counter(role.name for role in game.game_roles)
        # 2. Get ALIVE counts of each role (e.g., "Townie: 1")
        alive_role_counts = Counter(
            p.role.name for p in game.players.values() if p.is_alive and p.role
        )
        # 3. Prepare the dictionary for grouping
        roles_by_alignment = defaultdict(list)
        # 4. Loop through the TOTAL roles list
        #    (We loop this one to make sure roles with 0 alive are included!)
        for role_name, total_count in total_role_counts.items():
            # Get the alive count (defaults to 0 if none are alive)
            alive_count = alive_role_counts[role_name]
            # Find a sample role to get its alignment (same as your old code)
            sample_role = next((r for r in game.game_roles if r.name == role_name), None)
            if sample_role:
                alignment = sample_role.alignment
                # Format the new string based on if anyone is alive
                if alive_count == 0:
                    role_str = f"- ~~{role_name}~~ _Alive: 0 / Total: {total_count}_"
                else:
                    role_str = f"- {role_name} _Alive: {alive_count} / Total: {total_count}_"
                # Append to the correct alignment group
                roles_by_alignment[alignment].append(role_str)
        # --- Create Embed to be sent ---
        # Build the embed to display the role list (same as your old code)
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
        # Send the embed publicly in the channel
        await interaction.response.send_message(embed=embed, ephemeral=False)
        logger.info(f"Successfully sent role list to {interaction.user.name}.")

# --- Command to show all available commands ---
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
            "`/mafiastatus` - See the current game status (living/dead players).\n"
            "`/vote` - Vote to lynch a player during the day.\n"
            "`/mafiacount` - See the current vote tally.\n"
            "`/myrole` - (DM Only) Have your role resent to you.\n"
            "`/mafiarules` - Read the game rules.\n"
            "`/mafiaroles` - See roles in the current game (with alive/total counts).\n"
            "`/gamestats` - View statistics from all completed games.\n"
            "`/playerstats` - View any player's game statistics.\n"
        #    "`/skillscore` - View your (or another player's) skill score."  -- Commented out until implemented
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
            "`/forcephaseend` - Forcibly end the current Day or Night phase.\n"
            "`/mafiareinit` - (Debug) Rebuild player list from roles."
        )
        embed.add_field(name="Admin Commands", value=admin_commands, inline=False)
        # Send the embed as an ephemeral message
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Successfully sent command list to {interaction.user.name}.")

async def setup(bot):
    """The setup function required by discord.py to load the cog."""
    await bot.add_cog(InfoCog(bot))

