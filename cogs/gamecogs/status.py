# cogs/gamecogs/status.py
import logging
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def status_command(self, interaction: discord.Interaction):
    """Displays a public summary of the game state (living/dead players)."""
    logger.info(f"'/mafiastatus' command invoked by {interaction.user.name}.")
    game = getattr(self.bot, 'game_instance', None) or getattr(self, 'game', None)
    if not game or not game.game_settings.get("game_started"):
        await interaction.response.send_message("❌ There is no game currently running.", ephemeral=True)
        return

    status_message = game.get_status_message()
    await interaction.response.send_message(status_message, ephemeral=False)

