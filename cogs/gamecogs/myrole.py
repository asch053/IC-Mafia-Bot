# cogs/gamecogs/myrole.py
import logging
import discord
from utils.sendroledm import send_role_dm

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def myrole_command(self, interaction: discord.Interaction):
    """Allows a player to have their role card resent in a DM."""
    logger.info(f"'/myrole' command invoked by {interaction.user.name} in DMs.")
    if interaction.guild:
        await interaction.response.send_message("This command can only be used in DMs.", ephemeral=True)
        return

    game = getattr(self.bot, 'game_instance', None) or getattr(self, 'game', None)
    if not game:
        await interaction.response.send_message("No game is currently active.", ephemeral=True)
        return

    player_obj = game.players.get(interaction.user.id)
    if not player_obj or not player_obj.role:
        await interaction.response.send_message("You are not in the game or have no role.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    success = await send_role_dm(self.bot, player_obj, player_obj.role, game.guild)
    if success:
        await interaction.followup.send("Your role information has been resent.", ephemeral=True)
    else:
        await interaction.followup.send("I was unable to resend your role. Please check your privacy settings.", ephemeral=True)

