# cogs/gamecogs/vote.py
import logging
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def vote_command(self, interaction: discord.Interaction, player: str):
    """Processes a player's vote during the day phase."""
    logger.info(f"'/vote' command invoked by {interaction.user.name}, targeting '{player}'.")
    game = getattr(self.bot, 'game_instance', None) or getattr(self, 'game', None)
    if not game:
        await interaction.response.send_message("No game is currently active.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    message = await game.process_lynch_vote(interaction, interaction.user, player)
    await interaction.followup.send(message, ephemeral=True)

