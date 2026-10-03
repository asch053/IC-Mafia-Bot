# cogs/statscogs/leaderboard.py
import logging
from collections import defaultdict
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def handle_leaderboard(self, interaction: discord.Interaction, metric: str):
    """Displays a top 10 list based on the chosen metric."""
    await interaction.response.defer(ephemeral=False)

    games_by_mode = self._load_and_group_games()
    classic_games = games_by_mode.get('classic', [])
    if not classic_games:
        await interaction.followup.send("No 'Classic' mode games found to generate a leaderboard.", ephemeral=True)
        return

    player_stats = defaultdict(lambda: {"wins": 0, "games_played": 0, "survived": 0, "deaths": 0, "name": "Unknown"})

    for game in classic_games:
        for player in game.get('player_data', []):
            pid = player.get('player_id')
            if not pid or pid == "None":
                continue

            player_stats[pid]["games_played"] += 1
            player_stats[pid]["name"] = player.get('player_name', player_stats[pid]["name"])

            if player.get('is_winner'):
                player_stats[pid]["wins"] += 1
            if player.get('status') == "Alive":
                player_stats[pid]["survived"] += 1
            else:
                player_stats[pid]["deaths"] += 1

    min_games = 5
    filtered_players = {pid: stats for pid, stats in player_stats.items() if stats["games_played"] >= min_games}

    if not filtered_players:
        await interaction.followup.send(f"No players have played at least {min_games} games yet.", ephemeral=True)
        return

    leaderboard_data = []
    label = "Value"
    for pid, stats in filtered_players.items():
        if metric == "skill":
            value = (stats["wins"] / stats["games_played"] * 100) + (stats["survived"] / stats["games_played"] * 50)
            label = "Score"
        elif metric == "survivor":
            value = (stats["survived"] / stats["games_played"]) * 100
            label = "Survival Rate"
        elif metric == "red_shirt":
            value = (stats["deaths"] / stats["games_played"]) * 100
            label = "Death Rate"
        else:
            value = 0

        member = interaction.guild.get_member(pid) if interaction.guild else None
        name = member.display_name if member else stats["name"]
        leaderboard_data.append({"name": name, "value": value})

    leaderboard_data.sort(key=lambda x: x["value"], reverse=True)
    top_10 = leaderboard_data[:10]

    embed = discord.Embed(
        title=f"🏆 Top 10 Leaderboard: {metric.replace('_', ' ').title()}",
        color=discord.Color.gold(),
        description="Filtered by players with **>= 5 games** played."
    )

    for i, entry in enumerate(top_10, 1):
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        rank_display = medals.get(i, f"**{i}.**")
        val_str = f"{entry['value']:.1f}%" if "%" in label or "Rate" in label else f"{entry['value']:.1f}"
        embed.add_field(
            name=f"{rank_display} {entry['name']}",
            value=f"{label}: **{val_str}**",
            inline=False
        )

    await interaction.followup.send(embed=embed)

