# cogs/gamecogs/join.py
import logging
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def join_game_command(self, interaction: discord.Interaction):
    """Allows a player to sign up for an upcoming game."""
    logger.info(f"'/mafiajoin' command invoked by {interaction.user.name}.")
    game = getattr(self.bot, 'game_instance', None) or getattr(self, 'game', None)
    if game is None or game.game_settings.get("current_phase") != "signup":
        await interaction.response.send_message("There is no game currently accepting sign-ups.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    await game.add_player(interaction.user, interaction.user.display_name, interaction.channel)
    await interaction.followup.send("You've joined the game!", ephemeral=True)

