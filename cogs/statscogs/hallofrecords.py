# cogs/statscogs/hallofrecords.py
import logging
from collections import defaultdict
import discord
from utils.utilities import filter_games_by_time

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def handle_records(self, interaction: discord.Interaction, days: int = None):
    await interaction.response.defer(ephemeral=False)

    games_by_mode = self._load_and_group_games()
    raw_classic_games = games_by_mode.get('classic', [])
    classic_games = filter_games_by_time(raw_classic_games, days)

    if not classic_games:
        time_msg = f" in the last {days} days" if days else ""
        return await interaction.followup.send(f"No Classic mode game history found{time_msg}!")

    stats = defaultdict(lambda: {
        "name": "Unknown",
        "games": 0, "wins": 0, "losses": 0,
        "mob_games": 0, "town_games": 0, "plain_town_games": 0, "sk_games": 0,
        "mob_wins": 0, "town_wins": 0, "neutral_wins": 0,
        "night_deaths": 0, "n1_deaths": 0,
        "lynches": 0, "d1_lynches": 0
    })

    for game in classic_games:
        for p in game.get('player_data', []):
            pid = str(p.get('player_id'))
            if not pid or pid == "None":
                continue

            entry = stats[pid]
            entry['name'] = p.get('player_name', entry['name'])

            entry['games'] += 1
            is_winner = p.get('is_winner', False)
            if is_winner:
                entry['wins'] += 1
            else:
                entry['losses'] += 1

            alignment = p.get('alignment', '')
            role = p.get('role', '')

            if alignment == 'Mafia':
                entry['mob_games'] += 1
                if is_winner:
                    entry['mob_wins'] += 1
            elif alignment == 'Town':
                entry['town_games'] += 1
                if is_winner:
                    entry['town_wins'] += 1
            elif alignment in ['Serial Killer', 'Jester', 'Neutral']:
                entry['sk_games'] += 1
                if is_winner:
                    entry['neutral_wins'] += 1

            if role == 'Plain Townie':
                entry['plain_town_games'] += 1

            death_phase = p.get('death_phase', '') or ''
            death_cause = (p.get('death_cause', '') or '').lower()

            if death_phase.startswith('Night'):
                entry['night_deaths'] += 1
                if 'Night 1' in death_phase:
                    entry['n1_deaths'] += 1

            if 'lynch' in death_cause:
                entry['lynches'] += 1
                if 'Day 1' in death_phase:
                    entry['d1_lynches'] += 1

    def get_top(category_key):
        eligible = {pid: data for pid, data in stats.items() if data[category_key] > 0}
        if not eligible:
            return "Nobody yet!"
        max_val = max(data[category_key] for data in eligible.values())
        winners = [data['name'] for data in eligible.values() if data[category_key] == max_val]
        names_str = ", ".join(winners)
        return f"*{names_str}* ({max_val})"

    time_title = f" (Last {days} Days)" if days else " (All-Time)"
    embed = discord.Embed(
        title=f"🏆 Hall of Records{time_title}",
        description="The greatest highs and lowest lows across recorded Classic games.",
        color=discord.Color.purple()
    )

    embed.add_field(name="## Participation", value="\u200b", inline=False)
    embed.add_field(name="Most Games Played", value=get_top('games'), inline=True)
    embed.add_field(name="Most Wins", value=get_top('wins'), inline=True)
    embed.add_field(name="Most Losses", value=get_top('losses'), inline=True)

    embed.add_field(name="## Faction Loyalty", value="\u200b", inline=False)
    embed.add_field(name="Most Mafia Games", value=get_top('mob_games'), inline=True)
    embed.add_field(name="Most Town Games", value=get_top('town_games'), inline=True)
    embed.add_field(name="Most Neutral/SK Games", value=get_top('sk_games'), inline=True)

    embed.add_field(name="## Faction Success", value="\u200b", inline=False)
    embed.add_field(name="Most Mafia Wins", value=get_top('mob_wins'), inline=True)
    embed.add_field(name="Most Town Wins", value=get_top('town_wins'), inline=True)
    embed.add_field(name="Most Neutral/SK Wins", value=get_top('neutral_wins'), inline=True)

    embed.add_field(name="## Roles & Tragedy", value="\u200b", inline=False)
    embed.add_field(name="Most Plain Townie", value=get_top('plain_town_games'), inline=True)
    embed.add_field(name="Most Lynched", value=get_top('lynches'), inline=True)
    embed.add_field(name="Most Day 1 Lynches", value=get_top('d1_lynches'), inline=True)

    embed.add_field(name="## Turn 1 Tragedy", value="\u200b", inline=False)
    embed.add_field(name="Most Night Deaths", value=get_top('night_deaths'), inline=True)
    embed.add_field(name="Most Night 1 Deaths", value=get_top('n1_deaths'), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    await interaction.followup.send(embed=embed)

