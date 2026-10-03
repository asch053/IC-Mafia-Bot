import logging
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def force_start_command(self, interaction: discord.Interaction):
    """Command to bypass the signup timer and start the game on the next loop."""
    logger.info(f"'/forcestart' command invoked by {interaction.user.name}.")
    game = self.get_game_instance()
    if game is None:
        await interaction.response.send_message("No game is currently running to force start.", ephemeral=True)
        return

    if game and game.game_settings.get("current_phase") == "signup":
        await game.force_start(interaction)
    else:
        await interaction.response.send_message("No game is in the sign-up phase to force start.", ephemeral=True)

