import discord
import logging
from discord.ext import commands
from utils.utilities import load_data  # Import load_data

logger = logging.getLogger('discord')  # Get the SAME logger as in bot.py

class InfoCog(commands.Cog):
    """Cog for informational commands like /mafiarules, /mafiaroles, /mafiainfo"""

    def __init__(self, bot):
        self.bot = bot
        self.rules_text = load_data("data/rules.txt", "ERROR: rules.txt not found!")
        if isinstance(self.rules_text, list): # load_data returns list if txt
            self.rules_text = "\n".join(self.rules_text)  # Join into a single string
        # self.roles is already a global in game_engine.py, no need to load here.

    @commands.command(name="mafiarules")
    async def show_rules(self, ctx):
        """Displays the rules of the game."""
        await ctx.send(self.rules_text)

    @commands.command(name="mafiaroles")
    async def show_roles(self, ctx):
        """Displays the list of possible roles in the game."""
        # Assuming you have a way to access the *possible* roles (not the assigned ones).
        # This might be from your mafia_setups.json, or a separate roles.json,
        # or a hardcoded list.  This is a placeholder.
        all_roles = load_data("data/mafia_setups.json", "Error loading setups").get("7")[0].get("roles")
        if all_roles:
            role_list = "\n".join(f"- {role['name']}: {role['short_description']}" for role in all_roles)
            await ctx.send(f"**Possible Roles:**\n{role_list}")
        else:
            await ctx.send("No roles are defined.")


    @commands.command(name="mafiainfo")
    async def show_info(self, ctx):
        """Shows the list of available commands."""
        info_text = (
            "**Available Commands:**\n\n"
            "**Player Commands:**\n"
            "- `/mafiajoin` : Joins the upcoming game. Enter your game name as a parameter, which can be used during the game\n"
            "- `/mafiastatus`: Displays the current game status. Will show game names of all signed up players\n"
            "- `/vote <@player>`: Casts a vote during the day phase. Use either the players game name or discord ID (@name) to target\n"
            "- `/mafiacount`: Displays the current vote count.\n"
            "- `/mafiarules`: Displays the rules of the game.\n"
            "- `/mafiainfo`: Shows this help message.\n"
            "- `/mafiaroles`: Displays the list of possible roles in the game.\n"
            "- `/mafialeave`: Allows you to leave a game during setup phase only - Once a game starts you cannot use this function\n"
            " \n\n**Player Actions**\n"
            "- `/kill <@player>` (Godfather & Serial Killer only, DM only): Selects a player to be killed by the Mafia.\n"
            "- `/heal <@player>` (Doctor only, DM only): Selects a player to be healed.\n"
            "- `/investigate <@player>` (Town Cop only, DM only): Investigates a player's role.\n"
            "- `/block <@player>` (Roleblock only, DM only): Blocks a player's actions for the night.\n"
            "\n\n**Bot Admin Commands:**\n"
            "- `/mafiastart <start_datetime>  [phase_hours]`:  Starts a new game at the specified time. Date/time format: `YYYY-MM-DD HH:MM` (UTC).\n"
            "- `/mafiastop`: Stops the current game.\n"
            "- `/forcestart`: Forces the current sign-up period to end and the game to start.\n"
        )
        await ctx.send(info_text)
        logger.info("/info was called")

async def setup(bot):
  await bot.add_cog(InfoCog(bot))