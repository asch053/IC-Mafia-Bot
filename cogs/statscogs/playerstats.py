# cogs/statscogs/playerstats.py
import logging
import discord
from cogs.statscogs.loaders import get_player_games
from cogs.statscogs.calculators import build_player_stats_embed

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def handle_player_stats(self, interaction: discord.Interaction, player: str):
    logger.info(f"'/playerstats' invoked for ID {player}.")
    await interaction.response.defer(ephemeral=True)

    try:
        member = await interaction.guild.fetch_member(int(player))
    except (ValueError, discord.NotFound, Exception):
        await interaction.followup.send("Member not found.", ephemeral=True)
        return

    games_by_mode = self._load_and_group_games()
    player_games = get_player_games(games_by_mode, member.id)

    if not player_games:
        await interaction.followup.send(f"No game history found for **{member.display_name}**.", ephemeral=True)
        return

    embed = build_player_stats_embed(member, player_games)
    await interaction.followup.send(embed=embed, ephemeral=True)

