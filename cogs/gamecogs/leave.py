# cogs/gamecogs/leave.py
import logging
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def leave_game_command(self, interaction: discord.Interaction):
    """Allows a player to leave the game during sign-ups."""
    logger.info(f"'/mafialeave' command invoked by {interaction.user.name}.")
    game = getattr(self.bot, 'game_instance', None) or getattr(self, 'game', None)
    if game is None or game.game_settings.get("current_phase") != "signup":
        await interaction.response.send_message("There is no game to leave, or sign-ups are closed.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    await game.remove_player(interaction.user, interaction.channel)
    await interaction.followup.send("You've left the game.", ephemeral=True)

