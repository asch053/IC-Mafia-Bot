import logging
import discord
from cogs.admincogs.forcephaseend import force_phase_end_command

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def force_start_command(self, interaction: discord.Interaction):
    """Merged alias for /forcephaseend, immediately advancing whatever phase is active."""
    logger.info(f"'/forcestart' (merged) command invoked by {interaction.user.name}.")
    await force_phase_end_command(self, interaction)

