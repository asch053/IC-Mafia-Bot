# Cogs/stats.py
import discord
import os
import json
import logging
import math
from discord.ext import commands
from discord import app_commands
from collections import Counter, defaultdict
import config  # Import our config

# Get the logger from the main file
logger = logging.getLogger('discord')

class StatsCog(commands.Cog):
    def __init__(self, bot):
        logger.info("Initializing StatsCog...")
        self.bot = bot

    # --- Autocomplete Function ---
    async def player_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """An autocomplete provider that suggests server members."""
        logger.info("Providing autocomplete suggestions for input: " )
        choices = []
        # Ensure we have a guild context
        if not interaction.guild: 
            logger.warning("Autocomplete failed: No guild context.")
            return []
        # Search through guild members for matches
        for member in interaction.guild.members:
            # Case-insensitive match
            if current.lower() in member.display_name.lower() and not member.bot:
                choices.append(app_commands.Choice(name=member.display_name, value=str(member.id)))
        # Limit to top 25 choices
        return choices[:25]

    # --- HELPER: LOADS A SINGLE GAME FILE ---
    def _load_game_file(self, file_path: str) -> dict | None:
        """Loads a single JSON game file and returns its data."""
        logger.info(f"Loading game file: {file_path}")
        # Read and parse the JSON file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Loaded game file: {file_path}")
            return data
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from {file_path}")
        except Exception as e:
            logger.error(f"Error loading game file {file_path}: {e}")
        return None

    # --- HELPER: LOADS ALL GAME FILES ---
    def _load_and_group_games(self) -> list[dict]:
        """
        Loads all game summary files from all subdirectories in /stats/
        and returns them as a list of dictionaries.
        """
        logger.info("Loading all game logs...")
        all_games = []
        # Get the base stats directory from the config file
        stats_dir = config.data_save_path
        # Ensure the directory exists
        if not os.path.exists(stats_dir):
            logger.warning(f"Stats directory not found. => {stats_dir}")
            return []
        # os.walk will go through /Stats/Classic/, /Stats/Battle Royale/, etc.
        for root, dirs, files in os.walk(stats_dir):
            # Look for files ending with _summary.json
            for file in files:
                if file.endswith("_summary.json"):
                    file_path = os.path.join(root, file) # Construct full file path
                    game_data = self._load_game_file(file_path) # Load the game file
                    # Append to the list if loaded successfully
                    if game_data:
                        logger.info(f"Appending game data from file: {file_path}")
                        all_games.append(game_data) # Append the loaded game data to the list
        # Log the total number of game logs loaded and return the list
        logger.info(f"Loaded {len(all_games)} total game logs.")
        return all_games

    def _get_player_games(self, all_games_by_mode, player_id: int):
        """Filters all games to find only those a specific player was in."""
        # Build a dictionary of games per mode that include the player
        logger.info(f"Filtering games for player ID: {player_id}")
        player_games = defaultdict(list)
        # Iterate through each mode and its games
        for mode, games in all_games_by_mode.items(): 
            for game in games: # Check if player_id is in this game's player_data
                if any(p.get('player_id') == player_id for p in game['player_data']): # Player was in this game
                    player_games[mode].append(game) # Add the game to the player's list for this mode
                    logger.info(f"Found game for player ID {player_id} in mode '{mode}'.")
        logger.info(f"Total games found for player ID {player_id}: {sum(len(games) for games in player_games.values())}")
        return player_games # Return the dictionary of player games by mode

    def _calculate_win_rates(self, games, mode):
        """Calculates win counts and percentages for each faction, relevant to the mode."""
        # Early exit if no games
        logger.info(f"Calculating win rates for mode '{mode}'.")
        if not games: 
            logger.info(f"No games found for mode '{mode}'. Returning empty win rates.")
            return {}
        # Calculate total games and wins per faction/team
        total_games_in_mode = len(games) # Total games played in this mode
        wins = Counter() # Counter to tally wins per faction/team
        # Define valid winning factions per mode
        valid_winners = {
            'classic': {"Town", "Mafia", "Serial Killer", "Jester", "Draw"}, # Classic mode factions
            'battle_royale': {"Vigilante", "Draw"} # Battle Royale mode factions
        }
        # Tally wins for each faction/team
        for game in games: # Each game summary
            winner = game['game_summary']['winning_faction'] # Get the winning faction for this game
            if winner in valid_winners.get(mode, {}): # Only count valid winners for the mode
                wins[winner] += 1 # Increment win count for the winning faction/team
                logger.info(f"Incremented win count for '{winner}' in mode '{mode}'.")
        # Calculate win rates as percentages
        win_stats = {}
        # Loop through each faction/team and calculate stats
        for team, count in wins.items(): # Each faction/team that won
            rate = (count / total_games_in_mode) * 100 if total_games_in_mode > 0 else 0 # Calculate win rate percentage
            win_stats[team] = {'count': count, 'rate': rate} # Store count and rate in the stats dictionary
            logger.info(f"Calculated win rate for '{team}' in mode '{mode}': {count} wins, {rate:.1f}% rate.")
        logger.info(f"Completed win rate calculation for mode '{mode}'.")
        return win_stats

    def _calculate_player_stats(self, games, mode):
        """Calculates detailed per-player statistics, aware of the game mode."""
        player_stats = defaultdict(lambda: {'played': Counter(), 'wins': Counter(), 'total_games': 0}) # Default dict to hold player stats
        logger.info(f"Calculating player stats for mode '{mode}'.")
        # Iterate through each game
        for game in games: # Each game summary
            # Iterate through each player's data in the specific game for this loop
            logger.info(f"Processing game ID {game['game_summary'].get('game_id', 'N/A')} for player stats.")
            for p_data in game['player_data']: # Each player's data in the game
                logger.info(f"Processing player data: {p_data}")
                # Skip invalid or test data
                if mode == 'classic' and p_data.get('alignment') == 'Vigilante': continue # Skip old test data for classic mode
                # Extract player name and role/alignment key
                name = p_data['player_name'] # Get the player's display name
                key = p_data.get('alignment') # get the player's alignment
                # Special handling for Neutral Killing/Evil roles
                if p_data.get('alignment') in ['Serial Killer', 'Jester']: # if the players role is Neutral Killing/Evil roles
                    key = p_data.get('role') # Then Use role name instead of alignment
                # Skip if no valid role allignment/key found
                if not key: continue
                # Update stats for this player
                player_stats[name]['total_games'] += 1 # Increment total games played
                logger.info(f"Incremented total games for player '{name}' in mode '{mode}'.")
                player_stats[name]['played'][key] += 1 # Increment games played as this role/alignment
                logger.info(f"Incremented played count for player '{name}' as '{key}' in mode '{mode}'.")
                if p_data.get('is_winner'): # If this player won the game
                    player_stats[name]['wins'][key] += 1 # Increment wins as this role/alignment
                    logger.info(f"Incremented win count for player '{name}' as '{key}' in mode '{mode}'.")
        logger.info(f"Completed player stats calculation for mode '{mode}'.")
        return player_stats

    def _calculate_battle_royale_player_stats(self, games, player_id: int):
        """Calculates specific stats for a player in Battle Royale mode."""
        logger.info(f"Calculating Battle Royale stats for player ID: {player_id}")
        stats = {'played': 0, 'wins': 0, 'draws': 0, 'losses': 0} # Initialize stats dictionary
        # Iterate through each game
        for game in games: # Each game summary
            logger.info(f"Processing game ID {game['game_summary'].get('game_id', 'N/A')} for Battle Royale stats.")
            stats['played'] += 1 # Increment games played
            winner = game['game_summary'].get('winning_faction') # Get the winning player/faction for this game
            # Find this player's data in the game
            player_data = next((p for p in game['player_data'] if p.get('player_id') == player_id), None)
            if not player_data: continue # Skip if player data not found
            # Check if this player won, drew or lost the game
            if player_data.get('is_winner'): # If this player won
                stats['wins'] += 1 # Increment wins
                logger.info(f"Incremented win count for player ID {player_id}.")
            elif winner == "Draw": # If the game was a draw
                stats['draws'] += 1 # Increment draws
                logger.info(f"Incremented draw count for player ID {player_id}.")
            else: # Otherwise, the player lost
                stats['losses'] += 1 # Increment losses
                logger.info(f"Incremented loss count for player ID {player_id}.")
        logger.info(f"Completed Battle Royale stats calculation for player ID {player_id}.")
        return stats

    def _calculate_classic_player_stats(self, games, player_id: int):
        """Calculates specific stats for a player in Classic mode."""
        logger.info(f"Calculating Classic mode stats for player ID: {player_id}")
        # Initialize stats dictionary
        stats = {'played': 0, 'wins': 0, 'draws': 0, 'wins_by_faction': Counter(), 'games_as_faction': Counter()}
        # Iterate through each game
        for game in games: # Each game summary
            player_data = next((p for p in game['player_data'] if p.get('player_id') == player_id), None) # Find this player's data in the game
            if not player_data: continue # Skip if player data not found
            logger.info(f"Processing game ID {game['game_summary'].get('game_id', 'N/A')} for Classic mode stats.")
            # This is the crucial fix: skip old test data for classic mode
            if player_data.get('alignment') == 'Vigilante':
                logger.info(f"Skipping game ID {game['game_summary'].get('game_id', 'N/A')} due to Vigilante alignment (test data).")
                continue
            # Update stats for this player
            stats['played'] += 1 # Increment games played
            winner = game['game_summary'].get('winning_faction') # Get the winning faction for this game
            alignment = player_data.get('alignment') # get the player's alignment
            if alignment: # If the player has an alignment
                stats['games_as_faction'][alignment] += 1 # Increment games played as this faction/alignment
                logger.info(f"Incremented games played as '{alignment}' in Classic mode.")
            if player_data.get('is_winner'): # If this player won the game
                logger.info(f"Incremented win count for player ID {player_id} in Classic mode.")
                stats['wins'] += 1 # Increment wins
                if alignment: # If the player has an alignment
                    stats['wins_by_faction'][alignment] += 1 # Increment wins by this faction/alignment
                    logger.info(f"Incremented wins by '{alignment}' for player ID {player_id} in Classic mode.")
            elif winner == "Draw": # If the game was a draw
                logger.info(f"Incremented draw count for player ID {player_id} in Classic mode.")
                stats['draws'] += 1 # Increment draws
        logger.info(f"Completed Classic mode stats calculation for player ID {player_id}.")
        return stats

    def _build_player_stats_embed(self, member: discord.Member, player_games_by_mode):
        """Constructs the final embed for the /playerstats command."""
        # Initialize the embed
        logger.info(f"Building player stats embed for member: {member.display_name}")
        embed = discord.Embed(title=f"📊 Player Stats for {member.display_name}", color=discord.Color.purple()) # Set the title and color
        embed.set_thumbnail(url=member.display_avatar.url)
        # Calculate total games played
        total_games = sum(len(games) for games in player_games_by_mode.values())
        embed.description = f"Analyzed **{total_games}** game(s) played by {member.mention}." # Set the description
        # Early exit if no games found
        if not player_games_by_mode:
            embed.description += "\n\nNo game history found for this player."
            logger.warning(f"No game history found for {member.display_name}.")
            return embed
        # Loop through each mode and add stats fields
        if 'battle_royale' in player_games_by_mode: # If player has Battle Royale games
            logger.info(f"Processing Battle Royale stats for {member.display_name}.")
            br_games = player_games_by_mode['battle_royale'] # Get the Battle Royale games
            br_stats = self._calculate_battle_royale_player_stats(br_games, member.id) # Calculate Battle Royale stats
            win_pct = (br_stats['wins'] / br_stats['played'] * 100) if br_stats['played'] > 0 else 0 # Calculate win percentage
            draw_pct = (br_stats['draws'] / br_stats['played'] * 100) if br_stats['played'] > 0 else 0 # Calculate draw percentage
            loss_pct = (br_stats['losses'] / br_stats['played'] * 100) if br_stats['played'] > 0 else 0 # Calculate loss percentage
            logger.info(f"Battle Royale stats for {member.display_name}: {br_stats}")
            # Build the field value            
            value = (
                f"**Games Played:** {br_stats['played']}\n"
                f"**Win Rate:** {win_pct:.1f}% ({br_stats['wins']})\n"
                f"**Draw Rate:** {draw_pct:.1f}% ({br_stats['draws']})\n"
                f"**Loss Rate:** {loss_pct:.1f}% ({br_stats['losses']})"
            )
            embed.add_field(name="Battle Royale Stats", value=value, inline=False) # Add the field to the embed
        # Loop through each mode and add stats fields
        if 'classic' in player_games_by_mode: # If player has Classic mode games
            logger.info(f"Processing Classic mode stats for {member.display_name}.")
            classic_games = player_games_by_mode['classic'] # Get the Classic mode games
            classic_stats = self._calculate_classic_player_stats(classic_games, member.id) # Calculate Classic mode stats
            # Build the field value
            logger.info(f"Classic mode stats for {member.display_name}: {classic_stats}")
            if classic_stats['played'] > 0: # Only add if player has played Classic games
                win_pct = (classic_stats['wins'] / classic_stats['played'] * 100) # Calculate win percentage
                draw_pct = (classic_stats['draws'] / classic_stats['played'] * 100) # Calculate draw percentage
                # Build the field value
                value = (
                    f"**Games Played:** {classic_stats['played']}\n"
                    f"**Overall Win Rate:** {win_pct:.1f}% ({classic_stats['wins']})\n"
                    f"**Overall Draw Rate:** {draw_pct:.1f}% ({classic_stats['draws']})\n"
                )
                logger.info(f"Classic mode stats field value for {member.display_name}: {value}")
                if classic_stats['wins_by_faction']: # If there are wins by faction
                    value += "**Wins by Faction:**\n" # Add header for wins by faction
                    for faction, count in sorted(classic_stats['wins_by_faction'].items()): # Each faction and its win count
                        games_as = classic_stats['games_as_faction'].get(faction, 0) # Get games played as this faction
                        faction_win_pct = (count / games_as * 100) if games_as > 0 else 0 # Calculate win percentage for this faction
                        value += f"- {faction}: {count} win(s) ({faction_win_pct:.1f}% win rate as faction)\n" # Add faction win stats
                logger.info(f"Adding Classic mode stats field for {member.display_name}.")
                # Add the field to the embed
                embed.add_field(name="Classic Mode Stats", value=value, inline=False)
        logger.info(f"Completed building player stats embed for {member.display_name}.")
        return embed

    # --- OVERALL GAME STATS COMMAND ---
    # Statistics command to show overall game stats
    @app_commands.command(name="gamestats", description="Displays overall statistics from past games.")
    async def game_stats(self, interaction: discord.Interaction):
        """Calculates and displays overall game and player statistics, separated by mode."""
        logger.info(f"'/gamestats' command invoked by {interaction.user.name}.")
        # Defer the response to allow time for processing
        await interaction.response.defer(ephemeral=True)
        # Load and group all games by mode
        games_by_mode = self._load_and_group_games()
        # Check if we have any games
        if not games_by_mode:
            await interaction.followup.send("No game data found to generate statistics.", ephemeral=True)
            return
        # Calculate stats and build the embed
        total_games = sum(len(games) for games in games_by_mode.values())
        embed = discord.Embed(
            title="📊 Mafia Game Statistics",
            description=f"Analysis of **{total_games}** completed game(s) from the '{config.game_type}' dataset.",
            color=discord.Color.gold()
        )
        # Loop through each game mode and calculate stats
        for mode, games in sorted(games_by_mode.items()):
            mode_name = mode.replace('_', ' ').title()
            # Calculate win rates for factions/teams
            win_rates = self._calculate_win_rates(games, mode)
            # Add win rates to the embed
            if win_rates:
                win_rates_text = []
                for team, stats in sorted(win_rates.items(), key=lambda item: item[1]['count'], reverse=True):
                    win_rates_text.append(f"- **{team}**: {stats['count']} win(s) ({stats['rate']:.1f}%)")
                embed.add_field(name=f"🏆 {mode_name} Faction Win Rates ({len(games)} games)", value="\n".join(win_rates_text), inline=False)
            # Calculate player statistics       
            player_stats = self._calculate_player_stats(games, mode)
            # Sort and format player stats
            sorted_players = sorted(player_stats.items(), key=lambda item: item[1]['total_games'], reverse=True)
            player_stats_chunks = []
            current_chunk = ""
            for player_name, stats in sorted_players:
                if stats['total_games'] == 0: continue
                # Build the player stats block
                player_block = f"\n**{player_name}** ({stats['total_games']} games)\n"
                # Role distribution
                dist_parts = [f"{role} ({ (count / stats['total_games'] * 100):.0f}%)" for role, count in stats['played'].items()]
                player_block += f"> **Played:** {', '.join(dist_parts)}\n"
                # Win rate distribution
                win_rate_parts = []
                for role, wins in stats['wins'].items():
                    played_count = stats['played'].get(role, 0)
                    win_rate = (wins / played_count * 100) if played_count > 0 else 0
                    win_rate_parts.append(f"{role} ({win_rate:.0f}%)")
                if win_rate_parts:
                    player_block += f"> **Wins:** {', '.join(win_rate_parts)}\n"
                # Check if adding this block would exceed Discord's field limit
                if len(current_chunk) + len(player_block) > 1024:
                    player_stats_chunks.append(current_chunk)
                    current_chunk = player_block
                else:
                    current_chunk += player_block
            # Append any remaining chunk
            if current_chunk: player_stats_chunks.append(current_chunk)
            # Add player stats fields to the embed
            for i, chunk in enumerate(player_stats_chunks):
                field_name = f"👥 {mode_name} Player Stats"
                if len(player_stats_chunks) > 1: field_name += f" (Part {i+1})"
                if chunk: embed.add_field(name=field_name, value=chunk, inline=False)
        # Send the embed
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ---Statistics command to show individual player stats ---
    @app_commands.command(name="playerstats", description="Displays detailed statistics for a specific player.")
    @app_commands.describe(player="The server member you want to look up.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def playerstats(self, interaction: discord.Interaction, player: str):
        """New command to get stats for a single player."""
        logger.info(f"'/playerstats' command invoked by {interaction.user.name} for player ID {player}.")
        # Defer the response to allow time for processing
        await interaction.response.defer(ephemeral=True)
        # Fetch the member object from the guild
        try:
            logger.info(f"Fetching member with ID: {player}")
            member = await interaction.guild.fetch_member(int(player))
        except (ValueError, discord.NotFound):
            await interaction.followup.send("Could not find that member. Please select one from the list.", ephemeral=True)
            logger.warning(f"Could not find member with ID: {player}")
            return
        # Load and group all games by mode
        all_games = self._load_and_group_games()
        player_games = self._get_player_games(all_games, member.id)
        # Check if we have any games for this player
        if not player_games:
            await interaction.followup.send(f"No game history found for **{member.display_name}**.", ephemeral=True)
            logger.warning(f"No game history found for {member.display_name}.")
            return
        # Build and send the embed with player stats            
        embed = self._build_player_stats_embed(member, player_games)
        # Send the embed
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Successfully sent player stats for {member.display_name} to {interaction.user.name}.")
  
    # --- NEW SKILL SCORE COMMAND ---
    @app_commands.command(name="skillscore", description="Calculates a player's skill score for Classic mode.")
    @app_commands.describe(member="The player to look up (defaults to yourself).")
    async def skillscore(self, interaction: discord.Interaction, member: discord.User = None):
        """Calculates and displays a player's weighted skill score for Classic games."""
        await interaction.response.defer(ephemeral=True) # Defer response for processing time
        logger.info("Calculating skill score...")
        # Use the specified member or default to the command invoker
        target_member = member or interaction.user # Use the command invoker if no member specified
        logger.info(f"'/skillscore' command invoked for {target_member.display_name} by {interaction.user.name}.")
        # Calculate skill score
        try:
            # 1. Load all game files
            all_games = self._load_and_group_games()
            if not all_games: # No games found
                await interaction.followup.send("I couldn't find any game logs to analyze!", ephemeral=True)
                logger.warning("No game logs found for skill score calculation.")
                return
            # 2. FILTER FOR CLASSIC GAMES ONLY
            classic_games = []
            for game in all_games: # Each game summary
                game_type = game.get('game_summary', {}).get('game_type', 'classic') # Default to 'classic' if not specified
                if game_type.lower() == 'classic': # If this is a classic game
                    classic_games.append(game) # Add to classic games list
                    logger.info(f"Found classic game ID {game['game_summary'].get('game_id', 'N/A')}.")
            if not classic_games:
                await interaction.followup.send("I couldn't find any 'Classic' game logs for this player to analyze!", ephemeral=True)
                logger.warning("No 'Classic' game logs found for skill score calculation.")
                return
            # 3. Calculate all the scores (using ONLY the classic games)
            skill_data = self._calculate_skill_scores(target_member.id, classic_games) # Calculate skill scores
            logger.info(f"Calculated skill data for {target_member.display_name}: {skill_data}")
            # 4. Build the beautiful embed
            embed = discord.Embed(
                title=f"Skill Score (Classic Mode) for {target_member.display_name}",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=target_member.display_avatar.url)
            logger.info(f"Building skill score embed for {target_member.display_name}.")
            embed.add_field(
                name="🏆 Final Skill Score",
                value=f"**{skill_data['final_score']:.2f} / 5.00**",
                inline=False
            )
            # Add individual skill components
            # Add Persuasion
            embed.add_field(
                name="🧠 Persuasion",
                value=f"**{skill_data['persuasion_norm']:.2f} / 5.00**\n(Weighted Correctness * Decisiveness)",
                inline=True
            )
            # Add Elusiveness
            embed.add_field(
                name="🕶️ Elusiveness",
                value=f"**{skill_data['elusiveness_norm']:.2f} / 5.00**\n(Weighted Phase Survival)",
                inline=True
            )
            # Add Understanding
            embed.add_field(
                name="⚖️ Understanding",
                value=f"**{skill_data['understanding_norm']:.2f} / 5.00**\n(Weighted Win Rate in Impactful Games)",
                inline=True
            )
            # Add footer with game counts
            embed.set_footer(
                text=f"Analyzed {skill_data['total_games_played']} 'Classic' games ({skill_data['games_for_understanding']} were 'Impactful')"
            )
            # Send the embed
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Successfully sent skill score for {target_member.display_name} to {interaction.user.name}.")
        except Exception as e:
            logger.error(f"Error during /skillscore command: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred while calculating skill score: {e}", ephemeral=True)

    # --- NEW HELPER METHODS ---
    def _calculate_skill_scores(self, member_id: int, all_games: list) -> dict:
        """The main calculator. This gathers all data and computes the scores."""
        logger.info(f"Calculating skill scores for member ID: {member_id} over {len(all_games)} games.")
        # Initialize accumulators
        # --- Persuasion ---
        total_vote_switches = 0
        total_votes_cast = 0
        weighted_correct_votes_sum = 0
        weighted_total_votes_sum = 0
        # --- Elusiveness ---
        weighted_phases_survived_sum = 0
        weighted_total_phases_sum = 0
        # --- Understanding ---
        faction_games = defaultdict(int)
        faction_wins = defaultdict(int)
        total_games_played = 0
        games_for_understanding = 0
        # Process each game
        for game in all_games:
            player_game_data = None # Data for this player in the current game
            player_list = game.get('player_data', []) # List of all players in the game
            for p in player_list: # Find this player's data in the game
                # Handle old logs that might use 'player_name'
                if p.get('player_id') == member_id or p.get('player_name') == str(member_id): # Match found
                    logger.info(f"Found player ID {member_id} in game ID {game['game_summary'].get('game_id', 'N/A')}.")
                    player_game_data = p # Store the player's game data
                    break # No need to continue searching
            # Skip if player not in this game
            if not player_game_data:
                logger.info(f"Skipping game ID {game['game_summary'].get('game_id', 'N/A')} due to player ID {member_id} not being in the game.")
                continue # Player wasn't in this game
            logger.info(f"Processing game ID {game['game_summary'].get('game_id', 'N/A')} for player ID {member_id}.")
            total_games_played += 1 # Increment total games played
            # --- Common Data ---
            game_summary = game.get('game_summary', {}) # Summary data for the game
            # 1. Get total phases in this game
            total_phases_in_game = self._get_total_phases(player_list) # Total phases in the game
            if total_phases_in_game == 0: # Invalid game
                logger.info(f"Skipping game ID {game['game_summary'].get('game_id', 'N/A')} due to zero total phases.")
                continue # Skip malformed game                
            # 2. Get how long this player survived
            death_phase_str = player_game_data.get('death_phase') # Phase when player died (None if survived)
            phases_survived = total_phases_in_game # Default to full survival
            if death_phase_str: # Player died during the game
                logger.info(f"Player ID {member_id} died during phase {death_phase_str} in game ID {game['game_summary'].get('game_id', 'N/A')}.")
                phase_num = self._phase_str_to_int(death_phase_str) # Convert to integer phase number
                # If they died *during* phase 4, they only survived 3 phases
                phases_survived = max(0, phase_num - 1) # Survived up to the phase before death
            logger.info(f"Player ID {member_id} survived {phases_survived} out of {total_phases_in_game} phases in game ID {game['game_summary'].get('game_id', 'N/A')}.")
            # --- ELUSIVENESS CALC ---
            # Sum(1..N) is (n * (n+1)) / 2
            logger.info("Calculating elusiveness components...")
            weighted_survived = (phases_survived * (phases_survived + 1)) / 2 # Weighted survived calculation
            weighted_total = (total_phases_in_game * (total_phases_in_game + 1)) / 2 # Weighted total calculation
            logger.info(f"Weighted survived: {weighted_survived}, Weighted total: {weighted_total}")
            weighted_phases_survived_sum += weighted_survived # Accumulate weighted survived
            weighted_total_phases_sum += weighted_total # Accumulate weighted total
            logger.info(f"Accumulated weighted survived sum: {weighted_phases_survived_sum}, Accumulated weighted total sum: {weighted_total_phases_sum}")
            logger.info("Completed elusiveness calculation for this game.")
            # --- PERSUASION CALC ---
            logger.info("Calculating persuasion components...")
            # Get vote switches for this player in this game
            player_switches = game.get('vote_switch_history', {}).get(str(member_id), []) # Vote switches by this player
            total_vote_switches += len(player_switches) # Count of vote switches
            logger.info(f"Player ID {member_id} made {len(player_switches)} vote switches in game ID {game['game_summary'].get('game_id', 'N/A')}.")
            # Get all votes cast by this player in this game
            player_votes = [v for v in game.get('lynch_vote_history', []) if v.get('voter_id') == member_id] # Votes by this player
            total_votes_cast += len(player_votes) # Count of votes cast
            logger.info(f"Player ID {member_id} cast {len(player_votes)} votes in game ID {game['game_summary'].get('game_id', 'N/A')}.")
            # Group votes by phase
            votes_by_phase = defaultdict(list) # Votes organized by phase
            for v in player_votes: # Each vote by the player
                if v.get('phase'): # Ensure vote has a phase
                    votes_by_phase[v['phase']].append(v) # Group vote under its phase
            # --- THIS IS THE NEW FIX (thanks to you, cutie!) ---
            # Calculate *real* vote switches
            for phase_str, votes_in_phase in votes_by_phase.items():
                # We need at least 2 votes in a phase to *possibly* have a switch
                if len(votes_in_phase) > 1:
                    # Loop from the *second* vote onwards
                    for i in range(1, len(votes_in_phase)):
                        prev_vote_target = votes_in_phase[i-1].get('target_id')
                        current_vote_target = votes_in_phase[i].get('target_id')
                        
                        # Only count if the target is *different*!
                        if prev_vote_target != current_vote_target:
                            total_vote_switches += 1
            # --- END OF THE NEW FIX ---

            # Find the weighted correctness
            for phase_str, votes_in_phase in votes_by_phase.items(): # Each phase and its votes
                phase_num = self._phase_str_to_int(phase_str) # Convert phase string to integer
                if phase_num == 0 or phase_num % 2 != 0: # Not a Day phase
                    continue # Skip non-Day phases
                weighted_total_votes_sum += phase_num # Add weight just for voting
                final_vote_target = votes_in_phase[-1]['target_id'] # Last vote is the final target
                logger.info(f"Phase {phase_str}: Player voted for {final_vote_target}") # Log the final vote target
                # Get the lynched player for this phase
                lynched_player_id = self._get_lynched_player_for_phase(player_list, phase_str)
                # Check if the final vote was correct
                if final_vote_target == lynched_player_id and lynched_player_id is not None:
                    weighted_correct_votes_sum += phase_num # Add weight for being correct
                    logger.info(f"Phase {phase_str}: Correct vote by player {member_id} for lynching {lynched_player_id}")
            logger.info(f"Accumulated weighted correct votes sum: {weighted_correct_votes_sum}, Accumulated weighted total votes sum: {weighted_total_votes_sum}")
            logger.info("Completed persuasion calculation for this game.")
            # --- UNDERSTANDING CALC ---
            logger.info("Calculating understanding components...")
            # Determine if this game is "impactful"
            early_game_percent = getattr(config, "SKILL_EARLY_GAME_PERCENT", 0.25) # Default to 25% if not set
            early_game_cutoff = math.floor(total_phases_in_game * early_game_percent) # Calculate early game cutoff
            survived_past_early_game = phases_survived > early_game_cutoff # Check survival past early game
            logger.info(f"Early game cutoff: {early_game_cutoff}, Survived past early game: {survived_past_early_game}")
            # Check if player survived past early game OR if they won
            # (A win is always impactful, even if you die early!)
            player_won = player_game_data.get('is_winner', False) # Did the player win this game?
            logger.info(f"Player ID {member_id} won: {player_won}")
            if survived_past_early_game or player_won: # Impactful game
                games_for_understanding += 1 # Increment impactful games count
                alignment = player_game_data.get('alignment', 'Neutral') # Get player alignment
                # Normalize alignment to main factions
                if alignment not in ['Town', 'Mafia', 'Neutral']:
                    alignment = 'Neutral' # Group "Serial Killer", "Jester" etc.
                # Update faction games and wins
                faction_games[alignment] += 1 # Increment games played for this faction
                if player_won: # If this player won
                    faction_wins[alignment] += 1 # Increment wins for this faction
                logger.info(f"Updated faction stats for alignment '{alignment}': Games={faction_games[alignment]}, Wins={faction_wins[alignment]}")
            logger.info(f"Total impactful games for understanding so far: {games_for_understanding}")
            logger.info("Completed understanding calculation for this game.")
        # End of all games processing
        logger.info(f"Completed data accumulation for player ID {member_id}. Now calculating final scores.")
        # --- FINAL SCORE NORMALIZATION ---
        logger.info("Calculating final skill score components...")
        # Persuasion (0-1)
        logger.info("Calculating persuasion base...")
        persuasion_base = 0.0 # Base persuasion score
        logger.info(f"Weighted correct votes sum: {weighted_correct_votes_sum}, Weighted total votes sum: {weighted_total_votes_sum}")
        if weighted_total_votes_sum > 0: # Avoid division by zero
            persuasion_base = weighted_correct_votes_sum / weighted_total_votes_sum # Calculate base persuasion
            logger.info(f"Persuasion base: {persuasion_base}")
        # Decisiveness factor
        persuasion_decisiveness = 1.0 # Default decisiveness
        if total_votes_cast > 0: # Avoid division by zero
            persuasion_decisiveness = 1.0 - (total_vote_switches / total_votes_cast) # Calculate decisiveness
            logger.info(f"Persuasion decisiveness: {persuasion_decisiveness}")
        # Final persuasion score
        persuasion_score = persuasion_base * persuasion_decisiveness # Final persuasion calculation is product of base and decisiveness
        logger.info(f"Final persuasion score: {persuasion_score}")
        # Elusiveness (0-1) 
        elusiveness_score = 0.0 # Default elusiveness score
        if weighted_total_phases_sum > 0: # Avoid division by zero
            elusiveness_score = weighted_phases_survived_sum / weighted_total_phases_sum # Calculate elusiveness
            logger.info(f"Elusiveness score: {elusiveness_score}") 
        # Understanding (0-1)
        # NEW: Pull the faction weights from config
        w_town = getattr(config, "SKILL_WIN_WEIGHT_TOWN", 0.55) # Weight for Town wins
        w_mafia = getattr(config, "SKILL_WIN_WEIGHT_MAFIA", 0.35) # Weight for Mafia wins
        w_neutral = getattr(config, "SKILL_WIN_WEIGHT_NEUTRAL", 0.10) # Weight for Neutral wins
        understanding_score = 0.0 # Default understanding score
        if games_for_understanding > 0: # Avoid division by zero
            logger.info(f"Games for understanding: {games_for_understanding}")
            town_wr = 0.0 # Default Town win rate
            if faction_games['Town'] > 0: # If Town games were played
                town_wr = faction_wins['Town'] / faction_games['Town'] # Calculate Town win rate
            mafia_wr = 0.0 # Default Mafia win rate
            if faction_games['Mafia'] > 0: # If Mafia games were played
                mafia_wr = faction_wins['Mafia'] / faction_games['Mafia'] # Calculate Mafia win rate
            neutral_wr = 0.0 # Default Neutral win rate
            if faction_games['Neutral'] > 0: # If Neutral games were played
                neutral_wr = faction_wins['Neutral'] / faction_games['Neutral'] # Calculate Neutral win rate    
            logger.info(f"Win Rates - Town: {town_wr}, Mafia: {mafia_wr}, Neutral: {neutral_wr}")
            # The weighted formula from FR-5.5.4, now using config variables
            understanding_score = (mafia_wr * w_mafia) + (town_wr * w_town) + (neutral_wr * w_neutral) # Calculate understanding score
            logger.info(f"Understanding score: {understanding_score}")
        # NORMALIZE TO 5-POINT SCALE
        persuasion_norm = persuasion_score * 5 # Normalize persuasion to 5-point scale
        elusiveness_norm = elusiveness_score * 5 # Normalize elusiveness to 5-point scale
        understanding_norm = understanding_score * 5 # Normalize understanding to 5-point scale
        logger.info(f"Normalized Scores - Persuasion: {persuasion_norm}, Elusiveness: {elusiveness_norm}, Understanding: {understanding_norm}")
        # APPLY WEIGHTS FROM CONFIG.PY (FR-5.5.5)
        w_p = getattr(config, "SKILL_WEIGHT_PERSUASION", 1) # Weight for Persuasion
        w_e = getattr(config, "SKILL_WEIGHT_ELUSIVENESS", 1) # Weight for Elusiveness
        w_u = getattr(config, "SKILL_WEIGHT_UNDERSTANDING", 1) # Weight for Understanding
        total_weight = w_p + w_e + w_u # Total weight sum
        # Avoid division by zero
        if total_weight <= 0: 
            total_weight = 1
        # Final weighted score    
        final_score = ((persuasion_norm * w_p) + (elusiveness_norm * w_e) + (understanding_norm * w_u)) / total_weight
        final_score = min(final_score, 5.0) # Cap at 5
        logger.info(f"Final Skill Score for member ID {member_id}: {final_score}")
        # Return all relevant data
        return {
            "final_score": final_score,
            "persuasion_norm": persuasion_norm,
            "elusiveness_norm": elusiveness_norm,
            "understanding_norm": understanding_norm,
            "total_games_played": total_games_played,
            "games_for_understanding": games_for_understanding
        }

    def _phase_str_to_int(self, phase_str: str) -> int:
        """Converts a phase string like 'Day 2' or 'Night 1' into a number."""
        if not phase_str:
            return 0
        try:
            parts = phase_str.split(' ')
            if len(parts) != 2:
                return 0
            
            phase_type, phase_num_str = parts[0], parts[1]
            phase_num = int(phase_num_str)
            
            if phase_type.lower() == 'night':
                return (phase_num * 2) - 1
            elif phase_type.lower() == 'day':
                return phase_num * 2
            else:
                return 0
        except Exception as e:
            logger.warning(f"Could not parse phase string: {phase_str}. Error: {e}")
            return 0

    def _get_total_phases(self, player_list: list) -> int:
        """Finds the last phase a game ran to by checking the latest death."""
        logger.info("Calculating total phases in game based on player deaths.")
        # Iterate through all players to find the maximum death phase
        max_phase_num = 0 # Start with zero
        for p in player_list: # Each player in the game
            death_phase_str = p.get('death_phase') # Get the death phase string
            if death_phase_str: # If the player died
                phase_num = self._phase_str_to_int(death_phase_str) # Convert to integer phase number
                logger.info(f"Player ID {p.get('player_id')} died in phase {death_phase_str} (numeric: {phase_num})")
                max_phase_num = max(max_phase_num, phase_num) # Update max phase number
        logger.info(f"Total phases in game determined to be: {max_phase_num}")
        return max(1, max_phase_num)  # Ensure at least 1 phase

    def _get_lynched_player_for_phase(self, player_list: list, phase_str: str) -> int | None:
        """Finds who (if anyone) was lynched in a specific day phase."""
        logger.info(f"Searching for lynched player in phase: {phase_str}")
        # Iterate through all players to find the lynched player
        for p in player_list: # Each player in the game
            # THE FIX: Check if 'lynched' is *in* the death cause string!
            logger.info(f"Checking player {p.get('player_id')}, death_phase: {p.get('death_phase')}, death cause: {p.get('death_cause')}")
            if p.get('death_phase') == phase_str and 'lynched' in p.get('death_cause', '').lower(): # If this player was lynched in the specified phase
                logger.info(f"Lynched player in {phase_str} is {p.get('player_id')}") 
                return p.get('player_id')
        logger.info(f"No lynched player found in phase: {phase_str}")
        return None

# --- Setup Function ---
async def setup(bot):
    await bot.add_cog(StatsCog(bot))