import discord
from discord.ext import commands
import logging

# Get the same logger instance as in mafiabot.py
logger = logging.getLogger('discord')

class AdminCog(commands.Cog, name="AdminCog"):
    """Cog for all administrator and owner commands."""
    def __init__(self, bot):
        self.bot = bot
    def get_game_instance(self):
        """A helper method to safely get the game instance from GameCog."""
        game_cog = self.bot.get_cog('GameCog')
        if game_cog:
            return game_cog.game
        return None
    def set_game_instance(self, new_game_instance):
        """A helper method to safely set the game instance in GameCog."""
        game_cog = self.bot.get_cog('GameCog')
        if game_cog:
            game_cog.game = new_game_instance
            return True
        return False
    @commands.command(name="mafiastop")
    @commands.has_permissions(administrator=True)
    async def stop_game_command(self, ctx):
        """
        Stops the currently running game, resets all roles, and cleans up.
        """
        # Get the current game instance from the GameCog.
        game = self.get_game_instance()
        if game is None:
            await ctx.send("No game is currently running.")
            logger.info(f"/stop command used by {ctx.author.name}, but no game was running.")
            return
        # We call the game's own reset method. The game engine knows best how to clean itself up.
        await game.reset()
        # IMPORTANT: We now set the game instance in the GameCog back to None.
        # This frees up memory and allows a new game to be started.
        self.set_game_instance(None)
        await ctx.send("The current game has been stopped and all variables have been reset.")
        logger.info(f"The game was stopped by {ctx.author.name}.")

    @commands.command(name="mafiareinit")
    @commands.has_permissions(administrator=True)
    async def reinitialize_players(self, ctx):
        """
        (Mod Only) A debug tool to refresh the player list from Discord roles.
        This is useful for recovering from a crash or inconsistent state.
        """
        game = self.get_game_instance()
        if game is None:
            await ctx.send("No game is currently running to re-initialize.")
            return
        if not ctx.guild:
            await ctx.send("This command must be used in a server.")
            return
        living_role = ctx.guild.get_role(game.discord_role_data.get("living", {}).get("id", 0))
        dead_role = ctx.guild.get_role(game.discord_role_data.get("dead", {}).get("id", 0))
        if not living_role or not dead_role:
            await ctx.send("Error: 'Living Players' or 'Dead Players' roles could not be found.")
            return
        new_players = {}
        for member in ctx.guild.members:
            if living_role in member.roles or dead_role in member.roles:
                # Get the old player object to preserve role and death info if it exists
                old_player_obj = game.players.get(member.id)
                # Create a new Player object
                new_player_obj = game.player(user_id=member.id, discord_name=member.name, display_name=member.display_name)
                # Set the alive status based on their Discord role
                new_player_obj.is_alive = living_role in member.roles
                # If we have data from the old object, transfer it
                if old_player_obj:
                    new_player_obj.role = old_player_obj.role
                    new_player_obj.death_info = old_player_obj.death_info
                new_players[member.id] = new_player_obj
        # Replace the game's player dictionary with our newly constructed one
        game.players = new_players
        await ctx.send(f"Player dictionary re-initialized. Found {len(new_players)} players.")
        logger.warning(f"Player dictionary was manually re-initialized by {ctx.author.name}.")

    # In cogs/admin.py, inside the AdminCog class:
    @commands.command(name="forcestart")
    @commands.has_permissions(administrator=True)
    async def force_start_command(self, ctx):
        """Forces the current sign-up period to end and the game to start."""
        game = self.get_game_instance()
        if game:
            await game.force_start(ctx)
        else:
            await ctx.send("No game is currently in the sign-up phase.")

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
