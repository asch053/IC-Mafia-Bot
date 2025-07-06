import discord
import asyncio
import config
import logging

from discord.ext import commands
# Import the Game class, but not the standalone functions that will be deprecated
from game.engine import Game
import utils.utilities
from datetime import datetime, timezone

# Get the same logger instance as in mafiabot.py
logger = logging.getLogger('discord')

class GameCog(commands.Cog, name="GameCog"): # Added a name for clarity
    """Cog for all player-facing game commands."""
    def __init__(self, bot):
        self.bot = bot
        # This instance variable will hold the single, running Game object.
        # This is the correct way to manage state within a cog.
        self.game = None

    @commands.command(name="mafiastart")
    @commands.has_permissions(administrator=True) # It's good practice to keep permissions checks.
    async def start_game_command(self, ctx, phase_hours: float = config.PHASE_HOURS, *, start_datetime_str: str):
        """
        Starts a new Mafia game with a scheduled start time.
        Args:
            phase_hours: The number of hours each phase (day/night) will last.
            start_datetime_str: The datetime for the game start, format 'YYYY-MM-DD HH:MM' (UTC).
        """
        if self.game is not None:
            await ctx.send("A game is already in progress!")
            return
        # --- Input Validation ---
        try:
            # Add seconds to the format string for more precision if needed
            start_datetime_obj = datetime.strptime(start_datetime_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            await ctx.send("Invalid date/time format. Please use 'YYYY-MM-DD HH:MM' format in UTC.")
            return
        if start_datetime_obj <= datetime.now(timezone.utc):
            await ctx.send("The start time must be in the future.")
            return
        try:
            phase_hours = float(phase_hours)
            if phase_hours <= 0:
                raise ValueError("Phase duration must be positive.")
        except ValueError:
            await ctx.send("Invalid phase hours. Please provide a positive number.")
            return
        # --- Create and Start Game ---
        # Create a new Game instance and store it in this cog's state.
        self.game = Game(self.bot, ctx)
        logger.info(f"New game instance created by {ctx.author.name}.")
        # The 'start' method in the Game object now handles all announcements and waiting.
        await self.game.start(start_datetime_obj, phase_hours)


    @commands.command(name="mafiajoin")
    async def join_game_command(self, ctx):
        """Joins the current game during the sign-up phase."""
        if self.game is None:
            await ctx.send("No game is currently running or accepting sign-ups.")
            return
        # We call a method on the game instance to handle the logic.
        # This keeps the cog clean and the logic in the engine.
        await self.game.add_player(ctx.author, ctx.author.display_name)
        logger.info(f"{ctx.author.display_name} joined the game.")

    @commands.command(name="vote")
    async def vote(self, ctx, *, lynch_target_name: str):
        """Votes for a player during the day phase."""
        if self.game is None:
            await ctx.send("No game is currently running.")
            return
        # All logic is now handled by methods on the game instance.
        # This makes the code much more readable and less error-prone.
        await self.game.process_lynch_vote(ctx, ctx.author, lynch_target_name)
        logger.info(f"{ctx.author.name} voted to lynch {lynch_target_name}.")

    @commands.command(name="mafiacount")
    async def count_votes_command(self, ctx):
        """Displays the current vote count."""
        if self.game is None:
            await ctx.send("No game is currently running.")
            return
        # This method will fetch the current vote count from the game instance.
        logger.info(f"Vote count requested by {ctx.author.name}.")
        await self.game.send_vote_count(ctx.channel)

    @commands.command(name="mafiastatus")
    async def status_command(self, ctx):
        """Displays the current game status."""
        if self.game is None:
            await ctx.send("No game is currently running.")
            return
        # The game object itself should know how to format its status.
        logger.info(f"Game status requested by {ctx.author.name}.")
        status_message = self.game.get_status_message()
        await ctx.send(status_message)

    # --- Night Action Commands (DM Only) ---
    @commands.command(name="kill")
    @commands.dm_only()
    async def kill(self, ctx, *, target_name: str):
        """(DM Only) Action for roles that can kill, like Godfather or Serial Killer."""
        if self.game is None:
            await ctx.author.send("No game is currently running.")
            return
        # The game engine handles all the logic and permissions checks.
        # This method records the night action for the killer.
        # Note: The target_name should be validated to ensure it exists in the game.
        await self.game.record_night_action(
            ctx,
            player_id=ctx.author.id, 
            action_type='kill', 
            target_name=target_name
        )
        logger.info(f"{self.players[ctx.author.id]['role']} has requested to kill {target_name}.")
        
    @commands.command(name="heal")
    @commands.dm_only()
    async def heal(self, ctx, *, target_name: str):
        """(DM Only) Action for the Doctor to heal a player."""
        if self.game is None:
            await ctx.author.send("No game is currently running.")
            return
        # The game engine handles all the logic and permissions checks.
        # This method records the night action for the healer.
        await self.game.record_night_action(
            ctx,
            player_id=ctx.author.id, 
            action_type='heal', 
            target_name=target_name
        )
        logger.info(f"{self.players[ctx.author.id]['role']} has requested to heal {target_name}.")
    
    @commands.command(name="investigate")
    @commands.dm_only()
    async def investigate(self, ctx, *, target_name: str):
        """(DM Only) Action for the Town Cop to investigate a player."""
        if self.game is None:
            await ctx.author.send("No game is currently running.")
            return
        # The game engine handles all the logic and permissions checks.
        # This method records the night action for the investigator.
        await self.game.record_night_action(
            ctx,
            player_id=ctx.author.id, 
            action_type='investigate', 
            target_name=target_name
        )
        logger.info(f"{ctx.author.id} has requested to investigate {target_name}.")

# This function is called by mafiabot.py to load the cog.
async def setup(bot):
    await bot.add_cog(GameCog(bot))
