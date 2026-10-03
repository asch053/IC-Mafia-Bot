import logging
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def force_phase_end_command(self, interaction: discord.Interaction):
    """[ADMIN ONLY] Forcibly ends the current day or night phase."""
    logger.info(f"'/forcephaseend' command invoked by {interaction.user.name}.")
    game = self.get_game_instance()
    if game:
        await game.force_end_phase(interaction)
    else:
        await interaction.response.send_message("No game is currently active.", ephemeral=True)

