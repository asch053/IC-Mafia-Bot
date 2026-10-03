# cogs/statscogs/skillscore_calc.py
import math
import logging
from collections import defaultdict
import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def phase_str_to_int(phase_str: str) -> int:
    if not phase_str:
        return 0
    try:
        parts = phase_str.split(' ')
        if len(parts) != 2:
            return 0
        p_type, p_num = parts[0], int(parts[1])
        return (p_num * 2) - 1 if p_type.lower() == 'night' else p_num * 2
    except Exception:
        return 0


def get_total_phases(player_list: list) -> int:
    max_p = 0
    for p in player_list:
        if p.get('death_phase'):
            max_p = max(max_p, phase_str_to_int(p['death_phase']))
    return max(1, max_p)


def get_lynched_player_for_phase(player_list: list, phase_str: str) -> int | None:
    for p in player_list:
        if p.get('death_phase') == phase_str and 'lynched' in p.get('death_cause', '').lower():
            return p.get('player_id')
    return None


def calculate_skill_scores(member_id: int, games: list) -> dict:
    total_switches = 0
    total_votes = 0
    w_correct = 0
    w_total_vote = 0
    w_survived = 0
    w_total_phase = 0
    games_understanding = 0
    faction_games = defaultdict(int)
    faction_wins = defaultdict(int)
    played_count = 0

    early_pct = getattr(config, "SKILL_EARLY_GAME_PERCENT", 0.25)

    for game in games:
        players = game.get('player_data', [])
        p_data = next((p for p in players if p.get('player_id') == member_id or p.get('player_name') == str(member_id)), None)

        if not p_data:
            continue
        played_count += 1

        total_phases = get_total_phases(players)
        death = p_data.get('death_phase')
        survived = total_phases if not death else max(0, phase_str_to_int(death) - 1)

        w_survived += (survived * (survived + 1)) / 2
        w_total_phase += (total_phases * (total_phases + 1)) / 2

        my_votes = [v for v in game.get('lynch_vote_history', []) if v.get('voter_id') == member_id]
        total_votes += len(my_votes)

        by_phase = defaultdict(list)
        for v in my_votes:
            if v.get('phase'):
                by_phase[v['phase']].append(v)

        for phase, votes in by_phase.items():
            if len(votes) > 1:
                for i in range(1, len(votes)):
                    if votes[i - 1].get('target_id') != votes[i].get('target_id'):
                        total_switches += 1

            p_num = phase_str_to_int(phase)
            if p_num > 0 and p_num % 2 == 0:
                w_total_vote += p_num
                lynched = get_lynched_player_for_phase(players, phase)
                if votes[-1].get('target_id') == lynched:
                    w_correct += p_num

        cutoff = math.floor(total_phases * early_pct)
        won = p_data.get('is_winner', False)
        if survived > cutoff or won:
            games_understanding += 1
            align = p_data.get('alignment', 'Neutral')
            if align not in ['Town', 'Mafia', 'Neutral']:
                align = 'Neutral'
            faction_games[align] += 1
            if won:
                faction_wins[align] += 1

    p_base = (w_correct / w_total_vote) if w_total_vote > 0 else 0
    p_decis = 1.0 - (total_switches / total_votes) if total_votes > 0 else 1.0
    p_score = p_base * p_decis * 5

    e_score = (w_survived / w_total_phase * 5) if w_total_phase > 0 else 0

    u_score = 0
    if games_understanding > 0:
        w_town = getattr(config, "SKILL_WIN_WEIGHT_TOWN", 0.55)
        w_mafia = getattr(config, "SKILL_WIN_WEIGHT_MAFIA", 0.35)
        w_neut = getattr(config, "SKILL_WIN_WEIGHT_NEUTRAL", 0.10)
        rates = []
        for f, w in [('Town', w_town), ('Mafia', w_mafia), ('Neutral', w_neut)]:
            if faction_games[f] > 0:
                rates.append((faction_wins[f] / faction_games[f]) * w)
        u_score = sum(rates) * 5

    W_P = getattr(config, "SKILL_WEIGHT_PERSUASION", 1)
    W_E = getattr(config, "SKILL_WEIGHT_ELUSIVENESS", 1)
    W_U = getattr(config, "SKILL_WEIGHT_UNDERSTANDING", 1)

    final = ((p_score * W_P) + (e_score * W_E) + (u_score * W_U)) / (W_P + W_E + W_U)
    return {
        "final_score": min(final, 5.0),
        "persuasion_norm": p_score,
        "elusiveness_norm": e_score,
        "understanding_norm": u_score,
        "total_games_played": played_count,
        "games_for_understanding": games_understanding
    }

