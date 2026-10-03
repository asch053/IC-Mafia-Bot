# cogs/statscogs/gamestats.py
import logging
import discord
from cogs.statscogs.calculators import calculate_win_rates, calculate_player_stats

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def handle_game_stats(self, interaction: discord.Interaction):
    """Calculates and displays overall game and player statistics."""
    logger.info(f"'/gamestats' command invoked by {interaction.user.name}.")
    await interaction.response.defer(ephemeral=True)

    games_by_mode = self._load_and_group_games()
    if not games_by_mode:
        await interaction.followup.send("No game data found.", ephemeral=True)
        return

    total_games = sum(len(games) for games in games_by_mode.values())

    embed = discord.Embed(
        title="📊 Mafia Game Statistics",
        description=f"Analysis of **{total_games}** completed game(s).",
        color=discord.Color.gold()
    )

    for mode, games in sorted(games_by_mode.items()):
        mode_name = mode.replace('_', ' ').title()

        win_rates = calculate_win_rates(games, mode)
        if win_rates:
            text = []
            for team, stats in sorted(win_rates.items(), key=lambda x: x[1]['count'], reverse=True):
                text.append(f"- **{team}**: {stats['count']} ({stats['rate']:.1f}%)")
            embed.add_field(name=f"🏆 {mode_name} Win Rates ({len(games)} games)", value="\n".join(text), inline=False)

        p_stats = calculate_player_stats(games, mode)
        sorted_players = sorted(p_stats.items(), key=lambda x: x[1]['total_games'], reverse=True)
        top_5 = []
        for pid, data in sorted_players[:5]:
            top_5.append(f"**{data['name']}**: {data['total_games']} games")
        if top_5:
            embed.add_field(name=f"🎖️ Top Players ({mode_name})", value="\n".join(top_5), inline=False)

    await interaction.followup.send(embed=embed, ephemeral=True)

