import logging
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def stop_game_command(self, interaction: discord.Interaction):
    """Command to forcefully terminate and reset the current game."""
    logger.info(f"'/mafiastop' command invoked by {interaction.user.name}.")
    game = self.get_game_instance()
    if game is None:
        await interaction.response.send_message("No game is currently running.", ephemeral=True)
        return

    await interaction.response.send_message("🚨 **Game is being stopped by an administrator...**")
    await game.reset()
    self.set_game_instance(None)
    await interaction.channel.send("**Game has been stopped and reset.**")
    logger.warning(f"Game was forcibly stopped by admin: {interaction.user.name}.")