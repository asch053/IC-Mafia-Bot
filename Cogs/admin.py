import discord
from discord.ext import commands
import asyncio  # Import asyncio
# Import Game *class*, not the instance
from game.engine import Game #, stop_signup_task
import logging

# VERY IMPORTANT: We need a way to access the *global* Game instance.
# We'll use a global variable for this, BUT this is NOT ideal.
# A better solution would involve a more sophisticated way of managing
# the game state (e.g., a dedicated "GameManager" class).  But for
# simplicity, we'll use a global here.

game = None  # Global variable to hold the current game instance.
logger = logging.getLogger('discord')

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="stop")
    @commands.has_permissions(administrator=True)  # Example permission check
    async def stop_game_command(self, ctx):
      global game  # Access the global game variable
      if game is None:
          await ctx.send("No game is currently running.")
          logger.info("No game is currently running.")
          return
      # Get the current guild for role updates
      guild = ctx.guild
      if not guild:
          await ctx.send("This command can only be used in a server.")
          logger.info("This command (`/stop`) was used outside a server.")
          return
      # Call the reset method on the game instance.
      await game.reset(self.bot, guild)  # Pass bot and guild.
      game = None # IMPORTANT! Set game to None after stopping
      await ctx.send("The current game has been stopped.")
      logger.info("The current game has been stopped.")

    @commands.command(name="reinit_players")
    @commands.is_owner()
    async def reinitialize_players(self, ctx):
      """(Admin/Mod only) Re-initializes the player dictionary.
      Removes spectators and players without a role, updates display names,
      and keeps only players with "Living Players" or "Dead Players" roles.
      """
      global game
      if game is None: # Check if game exists
            await ctx.send("No game is currently running.")
            return
      guild = ctx.guild
      if not guild:
          await ctx.send("This command must be used in a server.")
          return
      living_role = discord.utils.get(guild.roles, id=game.discord_role_data.get("living", {}).get("id"))
      dead_role = discord.utils.get(guild.roles, id=game.discord_role_data.get("dead", {}).get("id"))
      if not living_role or not dead_role:
          await ctx.send("Error: 'Living Players' or 'Dead Players' roles not found.")
          return
      new_players = {}
      for member in guild.members:
          if living_role in member.roles or dead_role in member.roles:
              # Add player to the new dictionary, resetting relevant game data
              new_players[member.id] = {
                  "name": member.name,
                  "display_name": member.display_name,
                  "role": None,  # Reset role.
                  "alive": living_role in member.roles,  # Alive if they have living role.
                  "action_target": None,
                  "previous_target": None,
                  #Keep death info if player was dead
                  "death_info": game.players.get(member.id, {}).get("death_info", {}) if not living_role in member.roles else {}
              }
      game.players = new_players  # Replace the old dictionary with the new one.
      await ctx.send("Player dictionary reinitialized.")
      self.bot.logger.info("Player dictionary reinitialized by %s", ctx.author.name) # Use logger

async def setup(bot):
  await bot.add_cog(AdminCog(bot))