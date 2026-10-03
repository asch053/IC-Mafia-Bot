# cogs/infocogs/mafiarules.py
import logging
import discord
from game.data.getrules import build_rules_embed

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def show_rules_command(self, interaction: discord.Interaction):
    """Sends an ephemeral message to the user containing the game rules."""
    logger.info(f"'/mafiarules' command invoked by {interaction.user.name}.")
    try:
        game = getattr(self.bot, 'game_instance', None) or getattr(self, 'game', None)
        embed = build_rules_embed(self, game=game)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Successfully sent rules to {interaction.user.name}.")
    except Exception as e:
        logger.error(f"Failed to load rules for '/mafiarules' command: {e}", exc_info=True)
        await interaction.response.send_message("Sorry, I couldn't load the rules file at the moment.", ephemeral=True)

