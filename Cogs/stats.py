# Cogs/stats.py
import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
import os
from collections import Counter, defaultdict
import config # Import the config file

# Get the logger instance from the main bot file
logger = logging.getLogger('discord')

class StatsCog(commands.Cog, name="StatsCog"):
    """
    This cog handles all statistics-related commands, including overall
    game stats and individual player stats.
    """

    def __init__(self, bot: commands.Bot):
        """Initializes the StatsCog."""
        self.bot = bot
        # This is the fix! We point it to the main directory.
        self.stats_directory = "Stats"
        logger.info(f"StatsCog initialized. Watching directory: {self.stats_directory}")

    # --- Autocomplete Function ---
    async def player_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """An autocomplete provider that suggests server members."""
        choices = []
        if not interaction.guild: return []
        for member in interaction.guild.members:
            if current.lower() in member.display_name.lower() and not member.bot:
                choices.append(app_commands.Choice(name=member.display_name, value=str(member.id)))
        return choices[:25]

    # --- Helper Functions ---
    def _load_and_group_games(self):
        """Loads and groups all game summary files by game mode, normalizing old logs."""
        games_by_mode = defaultdict(list)
        if not os.path.exists(self.stats_directory): return {}

        for root, _, files in os.walk(self.stats_directory):
            for file in files:
                if file.endswith("_summary.json"):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r", encoding='utf-8') as f:
                            data = json.load(f)
                            if "game_summary" in data and "player_data" in data:
                                summary = data['game_summary']
                                mode = summary.get('game_type', 'classic')
                                winner = summary.get('winning_faction')
                                
                                known_factions = {"Town", "Mafia", "Draw", "Vigilante", "Serial Killer", "Jester"}
                                if mode == 'battle_royale' and winner not in known_factions:
                                    data['game_summary']['winning_faction'] = "Vigilante"
                                
                                games_by_mode[mode].append(data)
                    except Exception as e:
                        logger.error(f"Error loading file {filepath}: {e}", exc_info=True)
        return games_by_mode

    def _get_player_games(self, all_games_by_mode, player_id: int):
        """Filters all games to find only those a specific player was in."""
        player_games = defaultdict(list)
        for mode, games in all_games_by_mode.items():
            for game in games:
                if any(p.get('player_id') == player_id for p in game['player_data']):
                    player_games[mode].append(game)
        return player_games

    def _calculate_win_rates(self, games, mode):
        """Calculates win counts and percentages for each faction, relevant to the mode."""
        if not games: return {}
        
        total_games_in_mode = len(games)
        wins = Counter()
        
        valid_winners = {
            'classic': {"Town", "Mafia", "Serial Killer", "Jester", "Draw"},
            'battle_royale': {"Vigilante", "Draw"}
        }
        
        for game in games:
            winner = game['game_summary']['winning_faction']
            if winner in valid_winners.get(mode, {}):
                wins[winner] += 1
        
        win_stats = {}
        for team, count in wins.items():
            rate = (count / total_games_in_mode) * 100 if total_games_in_mode > 0 else 0
            win_stats[team] = {'count': count, 'rate': rate}
            
        return win_stats

    def _calculate_player_stats(self, games, mode):
        """Calculates detailed per-player statistics, aware of the game mode."""
        player_stats = defaultdict(lambda: {'played': Counter(), 'wins': Counter(), 'total_games': 0})
        
        for game in games:
            for p_data in game['player_data']:
                if mode == 'classic' and p_data.get('alignment') == 'Vigilante': continue

                name = p_data['player_name']
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
        """Calculates specific stats for a player in Battle Royale mode."""
        stats = {'played': 0, 'wins': 0, 'draws': 0, 'losses': 0}
        for game in games:
            stats['played'] += 1
            winner = game['game_summary'].get('winning_faction')
            
            player_data = next((p for p in game['player_data'] if p.get('player_id') == player_id), None)
            if not player_data: continue

            if player_data.get('is_winner'):
                stats['wins'] += 1
            elif winner == "Draw":
                stats['draws'] += 1
            else:
                stats['losses'] += 1
        return stats

    def _calculate_classic_player_stats(self, games, player_id: int):
        """Calculates specific stats for a player in Classic mode."""
        stats = {'played': 0, 'wins': 0, 'draws': 0, 'wins_by_faction': Counter(), 'games_as_faction': Counter()}
        for game in games:
            player_data = next((p for p in game['player_data'] if p.get('player_id') == player_id), None)
            if not player_data: continue
            
            # This is the crucial fix: skip old test data for classic mode
            if player_data.get('alignment') == 'Vigilante':
                continue
                
            stats['played'] += 1
            winner = game['game_summary'].get('winning_faction')
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
        """Constructs the final embed for the /playerstats command."""
        embed = discord.Embed(
            title=f"📊 Player Stats for {member.display_name}",
            color=discord.Color.purple()
        )
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
            draw_pct = (br_stats['draws'] / br_stats['played'] * 100) if br_stats['played'] > 0 else 0
            loss_pct = (br_stats['losses'] / br_stats['played'] * 100) if br_stats['played'] > 0 else 0
            
            value = (
                f"**Games Played:** {br_stats['played']}\n"
                f"**Win Rate:** {win_pct:.1f}% ({br_stats['wins']})\n"
                f"**Draw Rate:** {draw_pct:.1f}% ({br_stats['draws']})\n"
                f"**Loss Rate:** {loss_pct:.1f}% ({br_stats['losses']})"
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
                        faction_win_pct = (count / games_as * 100) if games_as > 0 else 0
                        value += f"- {faction}: {count} win(s) ({faction_win_pct:.1f}% win rate as faction)\n"
                
                embed.add_field(name="Classic Mode Stats", value=value, inline=False)
            
        return embed

    # --- Slash Commands ---
    @app_commands.command(name="gamestats", description="Displays overall statistics from past games.")
    async def game_stats(self, interaction: discord.Interaction):
        """Calculates and displays overall game and player statistics, separated by mode."""
        logger.info(f"'/gamestats' command invoked by {interaction.user.name}.")
        await interaction.response.defer(ephemeral=True)

        games_by_mode = self._load_and_group_games()
        if not games_by_mode:
            await interaction.followup.send("No game data found to generate statistics.", ephemeral=True)
            return

        total_games = sum(len(games) for games in games_by_mode.values())
        embed = discord.Embed(
            title="📊 Mafia Game Statistics",
            description=f"Analysis of **{total_games}** completed game(s) from the '{config.game_type}' dataset.",
            color=discord.Color.gold()
        )

        for mode, games in sorted(games_by_mode.items()):
            mode_name = mode.replace('_', ' ').title()
            
            win_rates = self._calculate_win_rates(games, mode)
            if win_rates:
                win_rates_text = []
                for team, stats in sorted(win_rates.items(), key=lambda item: item[1]['count'], reverse=True):
                    win_rates_text.append(f"- **{team}**: {stats['count']} win(s) ({stats['rate']:.1f}%)")
                embed.add_field(name=f"🏆 {mode_name} Faction Win Rates ({len(games)} games)", value="\n".join(win_rates_text), inline=False)

            player_stats = self._calculate_player_stats(games, mode)
            sorted_players = sorted(player_stats.items(), key=lambda item: item[1]['total_games'], reverse=True)
            
            player_stats_chunks = []
            current_chunk = ""
            for player_name, stats in sorted_players:
                if stats['total_games'] == 0: continue
                
                player_block = f"\n**{player_name}** ({stats['total_games']} games)\n"
                
                dist_parts = [f"{role} ({ (count / stats['total_games'] * 100):.0f}%)" for role, count in stats['played'].items()]
                player_block += f"> **Played:** {', '.join(dist_parts)}\n"
                
                win_rate_parts = []
                for role, wins in stats['wins'].items():
                    played_count = stats['played'].get(role, 0)
                    win_rate = (wins / played_count * 100) if played_count > 0 else 0
                    win_rate_parts.append(f"{role} ({win_rate:.0f}%)")
                if win_rate_parts:
                    player_block += f"> **Wins:** {', '.join(win_rate_parts)}\n"

                if len(current_chunk) + len(player_block) > 1024:
                    player_stats_chunks.append(current_chunk)
                    current_chunk = player_block
                else:
                    current_chunk += player_block
            
            if current_chunk: player_stats_chunks.append(current_chunk)

            for i, chunk in enumerate(player_stats_chunks):
                field_name = f"👥 {mode_name} Player Stats"
                if len(player_stats_chunks) > 1: field_name += f" (Part {i+1})"
                if chunk: embed.add_field(name=field_name, value=chunk, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="playerstats", description="Displays detailed statistics for a specific player.")
    @app_commands.describe(player="The server member you want to look up.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def playerstats(self, interaction: discord.Interaction, player: str):
        """New command to get stats for a single player."""
        logger.info(f"'/playerstats' command invoked by {interaction.user.name} for player ID {player}.")
        await interaction.response.defer(ephemeral=True)

        try:
            member = await interaction.guild.fetch_member(int(player))
        except (ValueError, discord.NotFound):
            await interaction.followup.send("Could not find that member. Please select one from the list.", ephemeral=True)
            return
            
        all_games = self._load_and_group_games()
        player_games = self._get_player_games(all_games, member.id)

        if not player_games:
            await interaction.followup.send(f"No game history found for **{member.display_name}**.", ephemeral=True)
            return
            
        embed = self._build_player_stats_embed(member, player_games)
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    """The setup function required by discord.py to load the cog."""
    await bot.add_cog(StatsCog(bot))

