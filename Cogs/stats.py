import discord
import os
import json
import logging
import math
from discord.ext import commands
from discord import app_commands
from collections import Counter, defaultdict
import config

logger = logging.getLogger('discord')

class StatsCog(commands.Cog):
    def __init__(self, bot):
        logger.info("Initializing StatsCog...")
        self.bot = bot

    async def player_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """An autocomplete provider that suggests server members."""
        choices = []
        if not interaction.guild: 
            return []
        for member in interaction.guild.members:
            if current.lower() in member.display_name.lower() and not member.bot:
                choices.append(app_commands.Choice(name=member.display_name, value=str(member.id)))
        return choices[:25]

    def _load_game_file(self, file_path: str) -> dict | None:
        """Loads a single JSON game file and returns its data."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error loading game file {file_path}: {e}")
        return None

    def _load_and_group_games(self) -> dict:
        """
        Loads all game logs and groups them by game mode.
        Returns: {'classic': [game1, game2], 'battle_royale': [game3]}
        """
        games_by_mode = defaultdict(list)
        stats_dir = config.data_save_path
        
        abs_path = os.path.abspath(stats_dir)
        logger.info(f"Searching for game logs in: {abs_path}")

        if not os.path.exists(stats_dir):
            logger.warning(f"Stats directory not found at: {abs_path}")
            return {}

        for root, dirs, files in os.walk(stats_dir):
            for file in files:
                if file.endswith("_summary.json"):
                    file_path = os.path.join(root, file)
                    game_data = self._load_game_file(file_path)
                    if game_data:
                        # Determine mode, defaulting to 'classic'
                        game_summary = game_data.get('game_summary', {})
                        mode = game_summary.get('game_type', 'classic').lower()
                        games_by_mode[mode].append(game_data)
        
        total_games = sum(len(g) for g in games_by_mode.values())
        logger.info(f"Loaded {total_games} total game logs.")
        return games_by_mode

    def _get_player_games(self, all_games_by_mode, player_id: int):
        """Filters all games to find only those a specific player was in."""
        player_games = defaultdict(list)
        for mode, games in all_games_by_mode.items(): 
            for game in games:
                # Check if player exists in the player_data list
                if any(p.get('player_id') == player_id for p in game.get('player_data', [])):
                    player_games[mode].append(game)
        return player_games

    def _calculate_win_rates(self, games, mode):
        """Calculates win counts and percentages for each faction."""
        if not games: return {}
        
        total_games = len(games)
        wins = Counter()
        
        valid_winners = {
            'classic': {"Town", "Mafia", "Serial Killer", "Jester", "Draw"},
            'battle_royale': {"Vigilante", "Draw"}
        }
        
        for game in games:
            winner = game.get('game_summary', {}).get('winning_faction')
            # Normalize winner string just in case
            if winner in valid_winners.get(mode, {}):
                wins[winner] += 1
                
        win_stats = {}
        for team, count in wins.items():
            rate = (count / total_games) * 100 if total_games > 0 else 0
            win_stats[team] = {'count': count, 'rate': rate}
            
        return win_stats

    def _calculate_player_stats(self, games, mode):
        """Calculates detailed per-player statistics."""
        player_stats = defaultdict(lambda: {'played': Counter(), 'wins': Counter(), 'total_games': 0})
        
        for game in games:
            for p_data in game.get('player_data', []):
                # Skip invalid/test data
                if mode == 'classic' and p_data.get('alignment') == 'Vigilante': continue
                
                name = p_data.get('player_name', 'Unknown')
                key = p_data.get('alignment')
                
                if p_data.get('alignment') in ['Serial Killer', 'Jester']:
                    key = p_data.get('role')
                
                if not key: continue
                
                player_stats[name]['total_games'] += 1
                player_stats[name]['played'][key] += 1
                if p_data.get('is_winner'):
                    player_stats[name]['wins'][key] += 1
                    
        return player_stats

    def _calculate_battle_royale_player_stats(self, games, player_id: int):
        stats = {'played': 0, 'wins': 0, 'draws': 0, 'losses': 0}
        for game in games:
            stats['played'] += 1
            winner = game.get('game_summary', {}).get('winning_faction')
            player_data = next((p for p in game.get('player_data', []) if p.get('player_id') == player_id), None)
            
            if not player_data: continue
            
            if player_data.get('is_winner'):
                stats['wins'] += 1
            elif winner == "Draw":
                stats['draws'] += 1
            else:
                stats['losses'] += 1
        return stats

    def _calculate_classic_player_stats(self, games, player_id: int):
        stats = {'played': 0, 'wins': 0, 'draws': 0, 'wins_by_faction': Counter(), 'games_as_faction': Counter()}
        for game in games:
            player_data = next((p for p in game.get('player_data', []) if p.get('player_id') == player_id), None)
            if not player_data: continue
            
            if player_data.get('alignment') == 'Vigilante': continue 

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

    def _build_player_stats_embed(self, member: discord.Member, player_games_by_mode):
        embed = discord.Embed(title=f"📊 Player Stats for {member.display_name}", color=discord.Color.purple())
        embed.set_thumbnail(url=member.display_avatar.url)
        
        total_games = sum(len(games) for games in player_games_by_mode.values())
        embed.description = f"Analyzed **{total_games}** game(s) played by {member.mention}."

        if not player_games_by_mode:
            embed.description += "\n\nNo game history found for this player."
            return embed

        if 'battle_royale' in player_games_by_mode:
            br_games = player_games_by_mode['battle_royale']
            br_stats = self._calculate_battle_royale_player_stats(br_games, member.id)
            win_pct = (br_stats['wins'] / br_stats['played'] * 100) if br_stats['played'] > 0 else 0
            
            value = (
                f"**Games Played:** {br_stats['played']}\n"
                f"**Win Rate:** {win_pct:.1f}% ({br_stats['wins']})\n"
                f"**Draws:** {br_stats['draws']} | **Losses:** {br_stats['losses']}"
            )
            embed.add_field(name="Battle Royale Stats", value=value, inline=False)

        if 'classic' in player_games_by_mode:
            classic_games = player_games_by_mode['classic']
            classic_stats = self._calculate_classic_player_stats(classic_games, member.id)
            
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

    # --- COMMANDS ---

    @app_commands.command(name="gamestats", description="Displays overall statistics from past games.")
    async def game_stats(self, interaction: discord.Interaction):
        """Calculates and displays overall game and player statistics."""
        logger.info(f"'/gamestats' command invoked by {interaction.user.name}.")
        await interaction.response.defer(ephemeral=True)

        # This returns a DICTIONARY {'mode': [games]}
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
            
            # Win Rates
            win_rates = self._calculate_win_rates(games, mode)
            if win_rates:
                text = []
                for team, stats in sorted(win_rates.items(), key=lambda x: x[1]['count'], reverse=True):
                    text.append(f"- **{team}**: {stats['count']} ({stats['rate']:.1f}%)")
                embed.add_field(name=f"🏆 {mode_name} Win Rates ({len(games)} games)", value="\n".join(text), inline=False)

            # Top Players
            p_stats = self._calculate_player_stats(games, mode)
            sorted_players = sorted(p_stats.items(), key=lambda x: x[1]['total_games'], reverse=True)
            
            top_5 = []
            for name, data in sorted_players[:5]:
                top_5.append(f"**{name}**: {data['total_games']} games")
            
            if top_5:
                embed.add_field(name=f"👥 Top {mode_name} Players", value="\n".join(top_5), inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="playerstats", description="Displays detailed statistics for a specific player.")
    @app_commands.describe(player="The server member you want to look up.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def playerstats(self, interaction: discord.Interaction, player: str):
        logger.info(f"'/playerstats' invoked for ID {player}.")
        await interaction.response.defer(ephemeral=True)

        try:
            member = await interaction.guild.fetch_member(int(player))
        except (ValueError, discord.NotFound):
            await interaction.followup.send("Member not found.", ephemeral=True)
            return

        games_by_mode = self._load_and_group_games()
        player_games = self._get_player_games(games_by_mode, member.id)
        
        if not player_games:
            await interaction.followup.send(f"No game history found for **{member.display_name}**.", ephemeral=True)
            return

        embed = self._build_player_stats_embed(member, player_games)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="skillscore", description="Calculates a player's skill score for Classic mode.")
    @app_commands.describe(member="The player to look up (defaults to yourself).")
    async def skillscore(self, interaction: discord.Interaction, member: discord.User = None):
        await interaction.response.defer(ephemeral=True)
        target = member or interaction.user
        
        # 1. Load all games (Dictionary)
        games_by_mode = self._load_and_group_games()
        
        if not games_by_mode:
            await interaction.followup.send("No game logs found to analyze.", ephemeral=True)
            return

        # 2. Extract ONLY Classic games safely
        # FIX: This is where the bug was. Use .get() instead of iterating.
        classic_games = games_by_mode.get('classic', [])
        
        if not classic_games:
             await interaction.followup.send("No 'Classic' mode games found.", ephemeral=True)
             return

        # 3. Calculate Score
        try:
            data = self._calculate_skill_scores(target.id, classic_games)
            
            embed = discord.Embed(title=f"Skill Score: {target.display_name}", color=discord.Color.gold())
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="🏆 Score", value=f"**{data['final_score']:.2f} / 5.0**", inline=False)
            embed.add_field(name="🧠 Persuasion", value=f"{data['persuasion_norm']:.2f}", inline=True)
            embed.add_field(name="🕶️ Elusiveness", value=f"{data['elusiveness_norm']:.2f}", inline=True)
            embed.add_field(name="⚖️ Understanding", value=f"{data['understanding_norm']:.2f}", inline=True)
            embed.set_footer(text=f"Based on {data['total_games_played']} Classic games.")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Skillscore error: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred while calculating skill score: {e}", ephemeral=True)

    # --- SKILL CALCULATION HELPERS ---
    def _phase_str_to_int(self, phase_str: str) -> int:
        if not phase_str: return 0
        try:
            parts = phase_str.split(' ')
            if len(parts) != 2: return 0
            p_type, p_num = parts[0], int(parts[1])
            return (p_num * 2) - 1 if p_type.lower() == 'night' else p_num * 2
        except: return 0

    def _get_total_phases(self, player_list: list) -> int:
        max_p = 0
        for p in player_list:
            if p.get('death_phase'):
                max_p = max(max_p, self._phase_str_to_int(p['death_phase']))
        return max(1, max_p)

    def _get_lynched_player_for_phase(self, player_list: list, phase_str: str) -> int | None:
        for p in player_list:
            if p.get('death_phase') == phase_str and 'lynched' in p.get('death_cause', '').lower():
                return p.get('player_id')
        return None

    def _calculate_skill_scores(self, member_id: int, games: list) -> dict:
        # --- Init Variables ---
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
            
            if not p_data: continue
            played_count += 1
            
            # Data Prep
            total_phases = self._get_total_phases(players)
            death = p_data.get('death_phase')
            survived = total_phases if not death else max(0, self._phase_str_to_int(death) - 1)
            
            # Elusiveness
            w_survived += (survived * (survived + 1)) / 2
            w_total_phase += (total_phases * (total_phases + 1)) / 2
            
            # Persuasion
            my_votes = [v for v in game.get('lynch_vote_history', []) if v.get('voter_id') == member_id]
            total_votes += len(my_votes)
            
            by_phase = defaultdict(list)
            for v in my_votes: 
                if v.get('phase'): by_phase[v['phase']].append(v)
            
            for phase, votes in by_phase.items():
                # Switches
                if len(votes) > 1:
                     for i in range(1, len(votes)):
                        if votes[i-1]['target_id'] != votes[i]['target_id']:
                            total_switches += 1
                
                # Correctness
                p_num = self._phase_str_to_int(phase)
                if p_num > 0 and p_num % 2 == 0: # Day only
                    w_total_vote += p_num
                    lynched = self._get_lynched_player_for_phase(players, phase)
                    if votes[-1]['target_id'] == lynched:
                        w_correct += p_num

            # Understanding
            cutoff = math.floor(total_phases * early_pct)
            won = p_data.get('is_winner', False)
            if survived > cutoff or won:
                games_understanding += 1
                align = p_data.get('alignment', 'Neutral')
                if align not in ['Town', 'Mafia', 'Neutral']: align = 'Neutral'
                faction_games[align] += 1
                if won: faction_wins[align] += 1

        # --- Final Math ---
        # Persuasion
        p_base = (w_correct / w_total_vote) if w_total_vote > 0 else 0
        p_decis = 1.0 - (total_switches / total_votes) if total_votes > 0 else 1.0
        p_score = p_base * p_decis * 5
        
        # Elusiveness
        e_score = (w_survived / w_total_phase * 5) if w_total_phase > 0 else 0
        
        # Understanding
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

        # Weights
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

async def setup(bot):
    await bot.add_cog(StatsCog(bot))