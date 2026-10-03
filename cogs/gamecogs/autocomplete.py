# cogs/gamecogs/autocomplete.py
import logging
import discord
from discord import app_commands

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def player_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """
    An autocomplete provider for slash commands. Suggests names of living players.
    """
    game = getattr(self.bot, 'game_instance', None) or getattr(self, 'game', None)
    if not game:
        return []
    choices = []
    living_players = [p.display_name for p in game.players.values() if p.is_alive]
    for player_name in living_players:
        if current.lower() in player_name.lower():
            choices.append(app_commands.Choice(name=player_name, value=player_name))
    return choices[:25]

