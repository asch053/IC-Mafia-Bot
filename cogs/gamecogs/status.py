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
    if len(status_message) <= 2000:
        await interaction.response.send_message(status_message, ephemeral=False)
    else:
        chunks = []
        current_chunk = ""
        for line in status_message.splitlines(keepends=True):
            if len(current_chunk) + len(line) > 1950:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += line
        if current_chunk:
            chunks.append(current_chunk)

        await interaction.response.send_message(chunks[0], ephemeral=False)
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk, ephemeral=False)

