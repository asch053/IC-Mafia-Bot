# Cogs/google_export.py
import discord
import os
import json
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from discord.ext import commands
from discord import app_commands
import config

# Get the logger from the main file
logger = logging.getLogger('discord')

class GoogleExportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        self.creds = None
        self.client = None
        try:
            # Authenticate with Google
            self.creds = ServiceAccountCredentials.from_json_keyfile_name(
                config.GOOGLE_CREDENTIALS_FILE, self.scope
            )
            self.client = gspread.authorize(self.creds)
            logger.info("Successfully authenticated with Google Sheets API.")
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Sheets: {e}")
            logger.error(f"Make sure '{config.GOOGLE_CREDENTIALS_FILE}' is in the bot's root directory.")
            logger.error("Make sure the Service Account email has Editor access to the Google Sheet.")

    # --- HELPER: LOADS A SINGLE GAME FILE ---
    # (This is borrowed from our StatsCog!)
    def _load_game_file(self, file_path: str) -> dict | None:
        """Loads a single JSON game file and returns its data."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from {file_path}")
        except Exception as e:
            logger.error(f"Error loading game file {file_path}: {e}")
        return None

    # --- HELPER: LOADS ALL GAME FILES ---
    # (This is also borrowed from our StatsCog!)
    def _load_and_group_games(self) -> list[dict]:
        """Loads all game summary files from all subdirectories in /Stats/"""
        all_games = []
        stats_dir = config.data_save_path
        if not os.path.exists(stats_dir):
            logger.warning("Stats directory not found.")
            return []

        for root, dirs, files in os.walk(stats_dir):
            for file in files:
                if file.endswith("_summary.json"):
                    file_path = os.path.join(root, file)
                    game_data = self._load_game_file(file_path)
                    if game_data:
                        all_games.append(game_data)
        
        logger.info(f"Loaded {len(all_games)} total game logs.")
        return all_games

    # --- THE EXPORT COMMAND ---
    
    @app_commands.command(name="exportstats", description="[Admin] Exports all game stats to Google Sheets.")
    @app_commands.checks.has_permissions(administrator=True) # Admin only!
    async def export_stats(self, interaction: discord.Interaction):
        """[ADMIN] Flattens all JSON game logs and uploads them to Google Sheets."""
        
        if not self.client:
            await interaction.response.send_message(
                "Error: Bot is not authenticated with Google Sheets. Check the logs.",
                ephemeral=True
            )
            return

        # This will take a while, so defer the response!
        await interaction.response.defer(ephemeral=True)
        logger.info(f"'/exportstats' command invoked by {interaction.user.name}.")

        try:
            # 1. Load all our JSON data
            all_games = self._load_and_group_games()
            if not all_games:
                await interaction.followup.send("No game logs found to export!", ephemeral=True)
                return

            # 2. Open the Google Sheet
            sheet = self.client.open_by_key(config.GOOGLE_SHEET_ID)
            games_sheet = sheet.worksheet(config.GOOGLE_SHEET_GAMES_TAB)
            players_sheet = sheet.worksheet(config.GOOGLE_SHEET_PLAYERS_TAB)
            votes_sheet = sheet.worksheet(config.GOOGLE_SHEET_VOTES_TAB)

            # 3. Prepare the "Flattened" Data
            
            # --- Headers (The first row) ---
            games_headers = [
                "Game_ID", "Game_Type", "Start_Time_UTC", "End_Time_UTC", 
                "Total_Phases", "Winning_Faction"
            ]
            players_headers = [
                "Game_ID", "Player_ID", "Player_Name", "Role", "Alignment", 
                "Is_Winner", "Death_Phase", "Death_Cause"
            ]
            votes_headers = [
                "Game_ID", "Phase", "Voter_ID", "Voter_Name", "Target_ID", "Target_Name"
            ]

            # --- Data Rows ---
            games_rows = []
            players_rows = []
            votes_rows = []

            for game in all_games:
                game_summary = game.get('game_summary', {})
                game_id = game_summary.get('game_id', 'UNKNOWN')

                # A. Flatten the "Games" data
                games_rows.append([
                    game_id,
                    game_summary.get('game_type'),
                    game_summary.get('start_date_utc'),
                    game_summary.get('end_date_utc'),
                    game_summary.get('total_days'), # This is really "total night/day cycles"
                    game_summary.get('winning_faction')
                ])

                # B. Flatten the "Players" data
                for player in game.get('player_data', []):
                    players_rows.append([
                        game_id,
                        player.get('player_id'),
                        player.get('player_name'),
                        player.get('role'),
                        player.get('alignment'),
                        player.get('is_winner'),
                        player.get('death_phase'),
                        player.get('death_cause')
                    ])
                
                # C. Flatten the "Votes" data
                for vote in game.get('lynch_vote_history', []):
                    votes_rows.append([
                        game_id,
                        vote.get('phase'),
                        vote.get('voter_id'),
                        vote.get('voter_name'),
                        vote.get('target_id'),
                        vote.get('target_name')
                    ])

            # 4. Clear and Upload the Data
            logger.info("Clearing old data from Google Sheets...")
            games_sheet.clear()
            players_sheet.clear()
            votes_sheet.clear()

            logger.info(f"Uploading {len(games_rows)} games, {len(players_rows)} players, and {len(votes_rows)} votes...")
            
            # Add headers + data in one go
            games_sheet.append_rows([games_headers] + games_rows, value_input_option='USER_ENTERED')
            players_sheet.append_rows([players_headers] + players_rows, value_input_option='USER_ENTERED')
            votes_sheet.append_rows([votes_headers] + votes_rows, value_input_option='USER_ENTERED')

            logger.info("Successfully exported all stats to Google Sheets!")
            await interaction.followup.send(
                f"**Success!** Exported {len(games_rows)} games, {len(players_rows)} player entries, "
                f"and {len(votes_rows)} votes to the Google Sheet.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error during /exportstats command: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

# --- Setup Function ---
async def setup(bot):
    await bot.add_cog(GoogleExportCog(bot))