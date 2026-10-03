# cogs/gamecogs/nightactions.py
import logging
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def handle_night_action(self, interaction: discord.Interaction, action_type: str, target_name: str):
    """
    A generic handler for all night actions.
    Performs initial checks and passes the action to the game engine.
    """
    logger.info(f"Handling night action '{action_type}' from {interaction.user.name} on target '{target_name}'.")
    game = getattr(self.bot, 'game_instance', None) or getattr(self, 'game', None)
    if not game:
        await interaction.response.send_message("No game is currently running.", ephemeral=True)
        return

    if interaction.guild:
        await interaction.response.send_message("Night actions must be used in DMs.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=False)
    message = await game.record_night_action(interaction.user.id, action_type, target_name)
    await interaction.followup.send(message, ephemeral=False)

