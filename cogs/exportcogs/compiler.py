# cogs/exportcogs/compiler.py
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def compile_standard_data(games):
    """Compiles the standard historical tabs (Games, Players, Votes)."""
    games_rows = []
    players_rows = []
    votes_rows = []

    for game in games:
        summ = game.get('game_summary', {})
        gid = summ.get('game_id')

        # 1. Games Tab
        games_rows.append([
            gid,
            summ.get('game_type', 'classic'),
            summ.get('start_date_utc'),
            summ.get('end_date_utc'),
            summ.get('total_days'),
            summ.get('winning_faction')
        ])

        # 2. Players Tab
        for p in game.get('player_data', []):
            players_rows.append([
                gid,
                str(p.get('player_id')),
                p.get('player_name'),
                p.get('role'),
                p.get('alignment'),
                p.get('is_winner'),
                p.get('death_phase'),
                p.get('death_cause'),
                p.get('death_phase_number')
            ])

        # 3. Votes Tab
        votes = game.get('lynch_vote_history', [])
        for v in votes:
            votes_rows.append([
                gid,
                v.get('phase'),
                str(v.get('voter_id')),
                v.get('voter_name'),
                str(v.get('target_id')),
                v.get('target_name')
            ])

    return games_rows, players_rows, votes_rows


def compile_rules_data(games):
    """Compiles rules setup data from saved game summaries."""
    rules_rows = []
    for game in games:
        summ = game.get('game_summary', {})
        gid = summ.get('game_id')
        if not gid:
            continue

        def format_choice(val):
            if isinstance(val, bool):
                return "Yes" if val else "No"
            if isinstance(val, str):
                return "Yes" if val.lower() in ("yes", "true", "1") else "No"
            return "No"

        rules_rows.append([
            gid,
            summ.get('scheduled_at_utc', summ.get('start_date_utc', '')),
            summ.get('scheduled_by', 'System'),
            summ.get('game_type', 'classic'),
            summ.get('story_type', 'Classic Mafia'),
            summ.get('start_date_utc', ''),
            summ.get('phase_hours', ''),
            summ.get('mafia_ratio', ''),
            summ.get('town_cop_req', ''),
            summ.get('town_doctor_req', ''),
            summ.get('town_rb_req', ''),
            summ.get('mafia_rb_req', ''),
            summ.get('sk_player_count', ''),
            format_choice(summ.get('gf_investigate', False)),
            format_choice(summ.get('sk_investigate', False)),
            format_choice(summ.get('gf_night_immune', True)),
            format_choice(summ.get('sk_night_immune', True)),
            format_choice(summ.get('br_skip_day', False))
        ])
    return rules_rows


def compile_analytics_data(classic_games, stats_cog):
    """Compiles comprehensive advanced analytics per player."""
    player_map = defaultdict(lambda: {
        'id': None, 'name': None, 'games': 0, 'wins': 0,
        'phases_lived': 0, 'phases_possible': 0,
        'n1_deaths': 0, 'd1_lynches': 0,
        'death_type_mafia': 0, 'death_type_sk': 0, 'death_type_lynch': 0,
        'accurate_votes': 0, 'total_end_phase_votes': 0,
        'factions': defaultdict(int), 'role_max_survival': defaultdict(int),
        'town_games': 0, 'mob_games': 0, 'sk_games': 0, 'plain_town_games': 0,
        'town_wins': 0, 'mob_wins': 0, 'neutral_wins': 0, 'night_deaths': 0
    })

    for game in classic_games:
        players = game.get('player_data', [])
        total_phases = stats_cog._get_total_phases(players)
        player_alignments = {str(p.get('player_id')): p.get('alignment') for p in players}

        for p in players:
            pid = str(p.get('player_id'))
            if not pid or pid == "None":
                continue

            entry = player_map[pid]
            entry['id'] = pid
            entry['name'] = p.get('player_name', entry['name'])
            entry['games'] += 1

            if p.get('is_winner'):
                entry['wins'] += 1

            align = p.get('alignment', '')
            role = p.get('role', '')

            if align == 'Mafia':
                entry['mob_games'] += 1
                if p.get('is_winner'):
                    entry['mob_wins'] += 1
            elif align == 'Town':
                entry['town_games'] += 1
                if p.get('is_winner'):
                    entry['town_wins'] += 1
            elif align in ['Serial Killer', 'Jester', 'Neutral']:
                entry['sk_games'] += 1
                if p.get('is_winner'):
                    entry['neutral_wins'] += 1

            if role == 'Plain Townie':
                entry['plain_town_games'] += 1

            entry['factions'][align] += 1

            death_phase = p.get('death_phase')
            death_cause = (p.get('death_cause') or '').lower()

            if death_phase:
                phases_lived = max(0, stats_cog._phase_str_to_int(death_phase) - 1)
                if 'night 1' in death_phase.lower():
                    entry['n1_deaths'] += 1
                if 'day 1' in death_phase.lower() and 'lynch' in death_cause:
                    entry['d1_lynches'] += 1
            else:
                phases_lived = total_phases

            entry['phases_lived'] += phases_lived
            entry['phases_possible'] += total_phases

            if death_phase and death_phase.lower().startswith('night'):
                entry['night_deaths'] += 1

            if 'mafia' in death_cause:
                entry['death_type_mafia'] += 1
            elif 'serial killer' in death_cause or 'sk' in death_cause:
                entry['death_type_sk'] += 1
            elif 'lynch' in death_cause:
                entry['death_type_lynch'] += 1

            entry['role_max_survival'][role] = max(entry['role_max_survival'][role], phases_lived)

        votes_by_phase = defaultdict(list)
        for v in game.get('lynch_vote_history', []):
            votes_by_phase[v.get('phase')].append(v)

        for phase, votes in votes_by_phase.items():
            phase_final_votes = {}
            for v in votes:
                phase_final_votes[str(v.get('voter_id'))] = str(v.get('target_id'))

            for voter_id, target_id in phase_final_votes.items():
                if target_id and target_id not in ("None", "0"):
                    target_alignment = player_alignments.get(target_id)
                    voter_id_str = str(voter_id)
                    if voter_id_str in player_map:
                        player_map[voter_id_str]['total_end_phase_votes'] += 1
                        if target_alignment == "Mafia":
                            player_map[voter_id_str]['accurate_votes'] += 1

    analytics_rows = []
    for pid_str, data in player_map.items():
        skill_data = stats_cog._calculate_skill_scores(int(data['id']), classic_games)

        win_rate = (data['wins'] / data['games'] * 100) if data['games'] > 0 else 0
        surv_rate = (data['phases_lived'] / data['phases_possible'] * 100) if data['phases_possible'] > 0 else 0
        vote_accuracy = (data['accurate_votes'] / data['total_end_phase_votes'] * 100) if data['total_end_phase_votes'] > 0 else 0

        if data['factions']:
            best_faction = max(data['factions'], key=data['factions'].get)
            faction_str = f"{best_faction} ({data['factions'][best_faction]})"
        else:
            faction_str = "N/A"

        if data['role_max_survival']:
            best_role = max(data['role_max_survival'], key=data['role_max_survival'].get)
            role_str = f"{best_role} ({data['role_max_survival'][best_role]} phases)"
        else:
            role_str = "N/A"

        losses = data['games'] - data['wins']

        analytics_rows.append([
            str(data['id']),
            data['name'],
            round(skill_data['final_score'], 2),
            round(skill_data['persuasion_norm'], 2),
            round(skill_data['elusiveness_norm'], 2),
            round(skill_data['understanding_norm'], 2),
            data['games'],
            data['wins'],
            data['phases_lived'],
            data['phases_possible'],
            round(win_rate, 1),
            round(surv_rate, 1),
            data['n1_deaths'],
            data['d1_lynches'],
            data['death_type_mafia'],
            data['death_type_sk'],
            data['death_type_lynch'],
            round(vote_accuracy, 1),
            faction_str,
            role_str,
            losses,
            data['town_games'],
            data['mob_games'],
            data['sk_games'],
            data['plain_town_games'],
            data['town_wins'],
            data['mob_wins'],
            data['neutral_wins'],
            data['night_deaths']
        ])

    analytics_rows.sort(key=lambda x: float(x[2]), reverse=True)
    return analytics_rows

