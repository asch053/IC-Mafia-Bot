# cogs/statscogs/calculators.py
import logging
import discord
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def calculate_win_rates(games: list, mode: str) -> dict:
    """Calculates win counts and percentages for each faction."""
    if not games:
        return {}

    total_games = len(games)
    wins = Counter()
    valid_winners = {
        'classic': {"Town", "Mafia", "Serial Killer", "Jester", "Draw"},
        'battle_royale': {"Vigilante", "Draw"}
    }

    for game in games:
        winner = game.get('game_summary', {}).get('winning_faction')
        if winner in valid_winners.get(mode, set()):
            wins[winner] += 1

    win_stats = {}
    for team, count in wins.items():
        rate = (count / total_games) * 100 if total_games > 0 else 0
        win_stats[team] = {'count': count, 'rate': rate}

    return win_stats


def calculate_player_stats(games: list, mode: str) -> dict:
    """Calculates detailed per-player statistics, grouped by ID."""
    player_stats = defaultdict(lambda: {'played': Counter(), 'wins': Counter(), 'total_games': 0, 'name': 'Unknown'})

    for game in games:
        for p_data in game.get('player_data', []):
            if mode == 'classic' and p_data.get('alignment') == 'Vigilante':
                continue

            pid = str(p_data.get('player_id'))
            if not pid or pid == "None":
                continue

            name = p_data.get('player_name', 'Unknown')
            key = p_data.get('alignment')
            if p_data.get('alignment') in ['Serial Killer', 'Jester']:
                key = p_data.get('role')

            if not key:
                continue

            player_stats[pid]['name'] = name
            player_stats[pid]['total_games'] += 1
            player_stats[pid]['played'][key] += 1
            if p_data.get('is_winner'):
                player_stats[pid]['wins'][key] += 1

    return player_stats


def calculate_battle_royale_player_stats(games: list, player_id: int) -> dict:
    stats = {'played': 0, 'wins': 0, 'draws': 0, 'losses': 0}
    for game in games:
        stats['played'] += 1
        winner = game.get('game_summary', {}).get('winning_faction')
        player_data = next((p for p in game.get('player_data', []) if p.get('player_id') == player_id), None)
        if not player_data:
            continue

        if player_data.get('is_winner'):
            stats['wins'] += 1
        elif winner == "Draw":
            stats['draws'] += 1
        else:
            stats['losses'] += 1
    return stats


def calculate_classic_player_stats(games: list, player_id: int) -> dict:
    stats = {'played': 0, 'wins': 0, 'draws': 0, 'wins_by_faction': Counter(), 'games_as_faction': Counter()}
    for game in games:
        player_data = next((p for p in game.get('player_data', []) if p.get('player_id') == player_id), None)
        if not player_data:
            continue

        if player_data.get('alignment') == 'Vigilante':
            continue

        stats['played'] += 1
        winner = game.get('game_summary', {}).get('winning_faction')
        alignment = player_data.get('alignment')

        if alignment:
            stats['games_as_faction'][alignment] += 1

        if player_data.get('is_winner'):
            stats['wins'] += 1
            if alignment:
                stats['wins_by_faction'][alignment] += 1
        elif winner == "Draw":
            stats['draws'] += 1
    return stats


def build_player_stats_embed(member: discord.Member, player_games_by_mode: dict) -> discord.Embed:
    embed = discord.Embed(title=f"📊 Player Stats for {member.display_name}", color=discord.Color.purple())
    if hasattr(member, 'display_avatar') and hasattr(member.display_avatar, 'url'):
        embed.set_thumbnail(url=member.display_avatar.url)

    total_games = sum(len(games) for games in player_games_by_mode.values())
    embed.description = f"Analyzed **{total_games}** game(s) played by {member.mention}."

    if not player_games_by_mode:
        embed.description += "\n\nNo game history found for this player."
        return embed

    if 'battle_royale' in player_games_by_mode:
        br_games = player_games_by_mode['battle_royale']
        br_stats = calculate_battle_royale_player_stats(br_games, member.id)
        win_pct = (br_stats['wins'] / br_stats['played'] * 100) if br_stats['played'] > 0 else 0

        value = (
            f"**Games Played:** {br_stats['played']}\n"
            f"**Win Rate:** {win_pct:.1f}% ({br_stats['wins']})\n"
            f"**Draws:** {br_stats['draws']} | **Losses:** {br_stats['losses']}"
        )
        embed.add_field(name="Battle Royale Stats", value=value, inline=False)

    if 'classic' in player_games_by_mode:
        classic_games = player_games_by_mode['classic']
        classic_stats = calculate_classic_player_stats(classic_games, member.id)

        if classic_stats['played'] > 0:
            win_pct = (classic_stats['wins'] / classic_stats['played'] * 100)
            draw_pct = (classic_stats['draws'] / classic_stats['played'] * 100)

            value = (
                f"**Games Played:** {classic_stats['played']}\n"
                f"**Overall Win Rate:** {win_pct:.1f}% ({classic_stats['wins']})\n"
                f"**Overall Draw Rate:** {draw_pct:.1f}% ({classic_stats['draws']})\n"
            )

            if classic_stats['wins_by_faction']:
                value += "**Wins by Faction:**\n"
                for faction, count in sorted(classic_stats['wins_by_faction'].items()):
                    games_as = classic_stats['games_as_faction'].get(faction, 0)
                    f_win_pct = (count / games_as * 100) if games_as > 0 else 0
                    value += f"- {faction}: {count} ({f_win_pct:.0f}%)\n"

            embed.add_field(name="Classic Mode Stats", value=value, inline=False)

    return embed

