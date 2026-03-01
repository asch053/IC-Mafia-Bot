import discord
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from discord.ext import commands
from discord import app_commands
import config
from collections import defaultdict

# Get the logger from the main file
logger = logging.getLogger('discord')

class ExportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        self.creds = None
        self.client = None
        
        # Authenticate on startup
        try:
            self.creds = ServiceAccountCredentials.from_json_keyfile_name(
                config.GOOGLE_CREDENTIALS_FILE, self.scope
            )
            self.client = gspread.authorize(self.creds)
            logger.info("Successfully authenticated with Google Sheets API.")
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Sheets: {e}")
            logger.error(f"Ensure '{config.GOOGLE_CREDENTIALS_FILE}' is in the root and has correct permissions.")

    def _connect_to_sheet(self):
        """Helper to reconnect/get the sheet object safely."""
        try:
            # Re-authorize if token expired
            if self.creds.access_token_expired:
                self.client.login()
            
            sheet = None
            # Check for ID first
            if hasattr(config, 'GOOGLE_SHEET_ID'):
                try:
                    sheet = self.client.open_by_key(config.GOOGLE_SHEET_ID)
                    logger.info(f"✅ Connected by ID. Target Sheet: '{sheet.title}'")
                except gspread.SpreadsheetNotFound:
                    logger.error(f"❌ Config has GOOGLE_SHEET_ID ({config.GOOGLE_SHEET_ID}) but sheet was not found.")
                    raise
            else:
                logger.warning("⚠️ GOOGLE_SHEET_ID not found in config. Falling back to Name search.")
                sheet = self.client.open("IC Mafia Bot Results")
                logger.info(f"✅ Connected by Name. Target Sheet: '{sheet.title}'")

            # Debug log to ensure we are writing to the right place
            logger.info(f"📝 WRITING DATA TO: https://docs.google.com/spreadsheets/d/{sheet.id}")
            return sheet
        except Exception as e:
            logger.error(f"Could not connect to Google Sheet: {e}")
            raise e

    def _compile_standard_data(self, games):
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

    def _compile_analytics_data(self, classic_games, stats_cog):
        """
        Uses StatsCog to calculate Skill Scores and build the Analytics tab.
        """
        player_map = defaultdict(lambda: {
            "games": 0, "wins": 0, "phases_lived": 0, "phases_possible": 0,
            "n1_deaths": 0, "d1_lynches": 0, 
            "death_type_mafia": 0, "death_type_sk": 0, "death_type_lynch": 0,
            "id": None, "name": None
        })

        # PASS 1: Aggregation
        for game in classic_games:
            total_phases = stats_cog._get_total_phases(game.get('player_data', []))
            
            for p in game.get('player_data', []):
                pid = p.get('player_id')
                name = p.get('player_name')
                if not pid or not name: continue
                
                entry = player_map[name]
                entry['id'] = pid
                entry['name'] = name
                entry['games'] += 1
                if p.get('is_winner'): entry['wins'] += 1
                
                # Phase Parsing via StatsCog
                phases_survived = total_phases
                death = p.get('death_phase')
                
                # Survival Logic
                if p.get('status') != "Alive" and not p.get('is_winner') and death:
                     phase_int = stats_cog._phase_str_to_int(death)
                     
                     # Calculate raw survival (died phase X, so survived X-1)
                     survived_raw = max(0, phase_int - 1)
                     
                     # FIX: Ensure a dead player NEVER gets 100% survival.
                     # We clamp their survived phases to be at most (Total - 1).
                     # max(0, ...) protects against 1-phase games crashing the math.
                     phases_survived = min(survived_raw, max(0, total_phases - 1))
                else:
                    # Alive or Winner = Full Survival
                    phases_survived = total_phases
                
                entry['phases_lived'] += phases_survived
                entry['phases_possible'] += total_phases
                
                if death:
                    if "Day 1" in death: entry['d1_lynches'] += 1
                    if "Night 1" in death: entry['n1_deaths'] += 1
                
                cause = (p.get('death_cause') or "").lower()
                if "mafia" in cause: entry['death_type_mafia'] += 1
                elif "sk" in cause or "serial" in cause: entry['death_type_sk'] += 1
                elif "lynch" in cause: entry['death_type_lynch'] += 1

        # PASS 2: Calculation & Formatting
        analytics_rows = []
        for name, data in player_map.items():
            # Calculate Skill Score using StatsCog
            skill_data = stats_cog._calculate_skill_scores(data['id'], classic_games)
            
            win_rate = (data['wins'] / data['games'] * 100) if data['games'] > 0 else 0
            surv_rate = (data['phases_lived'] / data['phases_possible'] * 100) if data['phases_possible'] > 0 else 0

            analytics_rows.append([
                name,
                round(skill_data['final_score'], 2),
                round(skill_data['persuasion_norm'], 2),
                round(skill_data['elusiveness_norm'], 2),
                round(skill_data['understanding_norm'], 2),
                data['games'],        # Already an int, no change needed!
                round(win_rate, 1),
                round(surv_rate, 1),
                data['n1_deaths'],    # Already an int
                data['d1_lynches'],   # Already an int
                data['death_type_mafia'], # Already an int
                data['death_type_sk'],    # Already an int
                data['death_type_lynch']  # Already an int
            ])
        
        # Sort by Skill Score Descending
        analytics_rows.sort(key=lambda x: float(x[1]), reverse=True)
        return analytics_rows

    async def run_export_logic(self):
        """
        The Master Trigger: Called manually or by the Game Engine.
        """
        if not self.client:
            return "❌ Google Client not authenticated."

        # 1. GET THE STATS COG
        stats_cog = self.bot.get_cog("StatsCog")
        if not stats_cog:
            return "❌ StatsCog not loaded. Cannot calculate scores."

        # 2. LOAD GAMES
        games_by_mode = stats_cog._load_and_group_games()
        
        # Flatten for standard tabs
        all_games = []
        for mode in games_by_mode:
            all_games.extend(games_by_mode[mode])
        
        # Get classic only for analytics
        classic_games = games_by_mode.get('classic', [])

        if not all_games:
            return "⚠️ No game data found to export."

        # 3. COMPILE ALL DATA
        games_rows, players_rows, votes_rows = self._compile_standard_data(all_games)
        analytics_rows = self._compile_analytics_data(classic_games, stats_cog)

        # 4. UPLOAD TO GOOGLE SHEETS
        try:
            sheet = self._connect_to_sheet()
            
            # Helper to update a tab safely
            async def update_tab(tab_name, headers, data):
                try:
                    ws = sheet.worksheet(tab_name)
                except gspread.WorksheetNotFound:
                    ws = sheet.add_worksheet(title=tab_name, rows=100, cols=20)
                ws.clear()
                if data:
                    ws.update(range_name='A1', values=[headers] + data)
                else:
                    ws.append_row(headers)

            # Update all 4 tabs
            await update_tab("Games", [
                "Game_ID", "Game_Type", "Start_Time_UTC", "End_Time_UTC", "Total_Days", "Winning_Faction"
            ], games_rows)
            
            await update_tab("Players", [
                "Game_ID", "Player_ID", "Player_Name", "Role", "Alignment", "Is_Winner", "Death_Phase", "Death_Cause"
            ], players_rows)
            
            await update_tab("Votes", [
                "Game_ID", "Phase", "Voter_ID", "Voter_Name", "Target_ID", "Target_Name"
            ], votes_rows)

            await update_tab("Analytics", [
                "Player Name", "Skill Score", "Persuasion (P)", "Elusiveness (E)", "Understanding (U)",
                "Games Played", "Win Rate %", "Survival %", "N1 Deaths", "D1 Lynches",
                "Deaths by Mafia", "Deaths by SK", "Times Lynched"
            ], analytics_rows)

            return f"✅ Export Complete: {len(games_rows)} games processed."

        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            raise e

    @app_commands.command(name="exportstats", description="Force update the Google Sheet.")
    async def exportstats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            result = await self.run_export_logic()
            await interaction.followup.send(result, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Critical Export Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ExportCog(bot))