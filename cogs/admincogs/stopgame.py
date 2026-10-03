import logging
import discord


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)



async def stop_game_command(self, interaction: discord.Interaction):
        """Command to forcefully terminate and reset the current game."""
        logger.info(f"'/mafiastop' command invoked by {interaction.user.name}.")
        # Retrieve the current game instance
        game = self.get_game_instance()
        if game is None:
            # Inform the admin if no game is active to stop
            await interaction.response.send_message("No game is currently running.", ephemeral=True)
            return
        # Acknowledge the command publicly before performing the cleanup
        await interaction.response.send_message("🚨 **Game is being stopped by an administrator...**")
        # Call the game engine's reset method to handle role cleanup and task cancellation
        await game.reset()
        # Nullify the game instance in the GameCog to allow a new game to start
        self.set_game_instance(None) 
        # Confirm to the channel that the game has been stopped
        await interaction.channel.send("**Game has been stopped and reset.**")
        logger.warning(f"Game was forcibly stopped by admin: {interaction.user.name}.")