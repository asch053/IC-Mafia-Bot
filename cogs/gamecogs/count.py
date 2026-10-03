# cogs/gamecogs/count.py
import logging
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def count_votes_command(self, interaction: discord.Interaction):
    """Publicly displays the current vote count."""
    logger.info(f"'/mafiacount' command invoked by {interaction.user.name}.")
    game = getattr(self.bot, 'game_instance', None) or getattr(self, 'game', None)
    if not game:
        await interaction.response.send_message("No game is currently active.", ephemeral=True)
        return

    await game.send_vote_count(interaction.channel)
    await interaction.response.send_message("Vote count displayed.", ephemeral=True)

