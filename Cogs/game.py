import discord
import asyncio
import mafiaconfig as config
import logging

from discord.ext import commands
from game.engine import Game, start_new_game, join_game
from utils.utilities import load_data
from datetime import datetime, timezone

logger = logging.getLogger('discord')  # Get the SAME logger as in bot.py

class GameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.game = None  # Store the Game instance here
    @commands.command(name="startmafia")
    #@commands.has_permissions(administrator=True) # Example: Only admins can use.  Use more robust permission system.
    async def start_game_command(self, ctx, phase_hours: float = config.PHASE_HOURS, *, start_datetime: str):
        """Starts a new Mafia game.
        Args:
            ctx: The command context.
            phase_hours: The number of hours each phase (day/night) will last.
            start_datetime: The datetime string for when the game should start, in the format '%Y-%m-%d %H:%M'.
        """
        if self.game is not None:
            await ctx.send("A game is already in progress!")
            return
        # Parse the start_datetime string
        try:
            start_datetime_obj = datetime.strptime(start_datetime, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            await ctx.send("Invalid date/time format. Please use 'YYYY-MM-DD HH:MM' format in UTC.")
            return
        # Check if start_datetime is in the future
        if start_datetime_obj <= datetime.now(timezone.utc):
            await ctx.send("The start time must be in the future.")
            return
        try:
            phase_hours = float(phase_hours)
            if phase_hours <= 0:
                raise ValueError("Phase duration must be positive")
        except ValueError:
            await ctx.send("Invalid phase hours")
            return
        # Create and start the game
        self.game = Game(self.bot, ctx)  # Create a new Game instance
        await self.game.start(start_datetime_obj, phase_hours)

async def setup(bot):
    await bot.add_cog(GameCog(bot))
    @commands.command(name="join")
    async def join_game_command(self, ctx):
      """Joins the current game."""
      global game
      if game is None:
        await ctx.send("No game is currently running.")
        return
      await join_game(self.bot, ctx, game) # Pass the 'game' instance
    @commands.command(name="vote")
    #@commands.has_permissions(administrator=True) # Example: Only admins can start
    async def vote(self, ctx, *, lynch_target):
        """Votes for a player during the day phase."""
        global game
        if game is None:
            await ctx.send("No game is currently running.")
            return
        if game.current_phase != "day":
          await ctx.send("Can only vote during the day")
          return
        voter_id = ctx.author.id
        if voter_id not in game.players or not game.players[voter_id]["alive"]:
          await ctx.send("You are not able to vote in this game.")
          return
        target_id = await game.get_player_id_by_name(lynch_target)
        if target_id is None or not game.players[target_id]["alive"]:
          await ctx.send(f"Player {lynch_target} not found or is not a valid target")
          return
        await game.process_lynch_vote(ctx, voter_id, target_id) # vote handled in engine
        await self.send_vote_update(ctx.channel)  # Send vote update. ctx.channel is correct

    @commands.command(name="count")
    async def count_votes_command(self, ctx):
        """Displays the current vote count."""
        # No changes needed here, BUT you must define send_vote_update in this Cog!
        if game is None:
            await ctx.send("No game is currently running.")
            return
        await self.send_vote_update(ctx.channel)
    async def send_vote_update(self, channel):
      """Sends a vote update to the specified channel."""
      global game
      if game:
        message = game.get_vote_status()
        await channel.send(message)
      else:
         await channel.send("No game running.")

    @commands.command(name="status")
    #@commands.has_permissions(administrator=True)
    async def status_command(self, ctx):
        """Displays the current game status."""
        global game
        if game is not None:
            await ctx.send(game.get_status_message())
        else:
            await ctx.send("No game is currently running.")

    @commands.command(name="kill")
    @commands.dm_only()
    async def kill(self, ctx, *, target_name: str):
      global game
      if game is None:
        await ctx.author.send("No game is currently running.")
        return
      player_id = ctx.author.id
      if player_id not in game.players:
        await ctx.author.send("You are not part of the current game.")
        return
      if game.current_phase != "night":
        await ctx.author.send("You can only use this command during the night phase.")
        return
      if not game.players[player_id]["alive"]:
        await ctx.author.send("Dead players cannot use this command.")
        return
      allowed_roles = ["Godfather", "Serial Killer"]
      if game.players[player_id]["role"].name not in allowed_roles:
          await ctx.author.send("You do not have the required role to use this command.")
          return
      target_id = await game.get_player_id_by_name(target_name)
      if target_id is None:
          await ctx.author.send(f"Could not find a player named '{target_name}'.")
          return
      if target_id == player_id:
          await ctx.author.send("You cannot target yourself.")
          return
      if not game.players[target_id]["alive"]:
          await ctx.author.send("You cannot target dead players.")
          return
      if game.players[player_id]["role"].name == "Godfather":
          game.mob_target = target_id
          await ctx.author.send(f"Godfather has selected {game.players[target_id]['name']} as the target.")
      elif game.players[player_id]["role"].name == "Serial Killer":
          game.sk_target = target_id
          await ctx.author.send(f"Serial Killer has selected {game.players[target_id]['name']} as the target.")

    @commands.command(name="heal")
    @commands.dm_only()
    async def heal(self, ctx, *, target_name: str):
        global game
        if game is None:
            await ctx.author.send("No game is currently running")
            return
        player_id = ctx.author.id
        if player_id not in game.players:
          await ctx.author.send("You are not part of the current game.")
          return
        if game.current_phase != "night":
            await ctx.author.send("You can only use this command during the night phase.")
            return
        player_data = game.players[player_id]
        if not player_data["alive"]:
            await ctx.author.send("Dead players cannot use this command.")
            return
        allowed_roles = ["Doctor"]
        if player_data["role"].name not in allowed_roles:
            await ctx.author.send("You do not have the required role to use this command.")
            return
        target_id = await game.get_player_id_by_name(target_name)
        if target_id is None:
            await ctx.author.send(f"Could not find a player named '{target_name}'.")
            return
        if target_id == player_id:
            await ctx.author.send("You cannot target yourself.")
            return
        if not game.players[target_id]["alive"]:
            await ctx.author.send("You cannot target dead players.")
            return
        game.heal_target = target_id
        await ctx.author.send(f"You have chosen to heal {game.players[target_id]['name']}.")

    @commands.command(name="investigate")
    @commands.dm_only()
    async def investigate(self, ctx, *, target_name: str):
        global game
        if game is None:
          await ctx.author.send("No game is currently running")
          return
        player_id = ctx.author.id
        if player_id not in game.players:
          await ctx.author.send("You are not part of the current game")
          return
        if not game.current_phase == "night":
          await ctx.author.send("You can only use this command during the night phase.")
          return
        player_data = game.players[player_id]
        if not player_data["alive"]:
          await ctx.author.send("Dead players cannot use this command")
          return
        allowed_roles = ["Town Cop"]
        if player_data["role"].name not in allowed_roles:
          await ctx.author.send("You do not have the required role to use this command.")
          return
        target_id = await game.get_player_id_by_name(target_name)
        if target_id is None:
          await ctx.author.send("Could not find the target player")
          return
        if target_id == player_id:
            await ctx.author.send("You cannot target yourself.")
            return
        if not game.players[target_id]["alive"]:
            await ctx.author.send("You cannot target dead players.")
            return
        game.investigate_target = target_id
        await ctx.author.send("You have investigated {}".format(game.players[target_id]["name"]))

async def setup(bot):
  await bot.add_cog(GameCog(bot))