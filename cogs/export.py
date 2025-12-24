import discord
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from discord.ext import commands
from discord import app_commands
import config

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
            
            # Open the sheet by Key or Name (Configurable)
            # Assuming config has GOOGLE_SHEET_ID, otherwise use name
            if hasattr(config, 'GOOGLE_SHEET_ID'):
                return self.client.open_by_key(config.GOOGLE_SHEET_ID)
            else:
                return self.client.open("IC Mafia Bot Results") # Default name
        except Exception as e:
            logger.error(f"Could not connect to Google Sheet: {e}")
            raise e

    def _compile_standard_data(self, games):
        """
        Compiles the original 3 tabs: Games, Players, Votes.
        Preserves the exact format you used previously.
        """
        games_rows = []
        players_rows = []
        votes_rows = []

        for game in games:
            summ = game.get('game_summary', {})
            gid = summ.get('game_id')
            
            # 1. Games Tab Row
            # Headers: Game_ID, Game_Type, Start_Time_UTC, End_Time_UTC, Total_Phases, Winning_Faction
            games_rows.append([
                gid,
                summ.get('game_type', 'classic'),
                summ.get('start_date_utc'),
                summ.get('end_date_utc'),
                summ.get('total_days'), # Map total_days to Total_Phases
                summ.get('winning_faction')
            ])

            # 2. Players Tab Rows
            # Headers: Game_ID, Player_ID, Player_Name, Role, Alignment, Is_Winner, Death_Phase, Death_Cause
            for p in game.get('player_data', []):
                players_rows.append([
                    gid,
                    str(p.get('player_id')),
                    p.get('player_name'),
                    p.get('role'),
                    p.get('alignment'),
                    p.get('is_winner'),
                    p.get('death_phase'),
                    p.get('death_cause')
                ])

            # 3. Votes Tab Rows
            # Headers: Game_ID, Phase, Voter_ID, Voter_Name, Target_ID, Target_Name
            # Note: Checking 'lynch_vote_history' or generic 'vote_history'
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
        Compiles the NEW Analytics tab using StatsCog logic.
        """
        # We reuse the logic we wrote in the previous turn, but return a LIST of LISTS for gspread
        # instead of a list of dicts.
        
        # 1. Get the leaderboard data (List of Dicts) from our helper logic
        # We will adapt the logic here slightly to output list-of-lists directly
        
        from collections import defaultdict
        player_map = defaultdict(lambda: {
            "games": 0, "wins": 0, "phases_lived": 0, "phases_possible": 0,
            "n1_deaths": 0, "d1_lynches": 0, "death_type_mafia": 0, "death_type_sk": 0, "death_type_lynch": 0,
            "id": None, "name": None
        })

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
                
                phases_survived = total_phases
                death = p.get('death_phase')
                if p.get('status') != "Alive" and not p.get('is_winner') and death:
                     phases_survived = max(0, stats_cog._phase_str_to_int(death) - 1)
                
                entry['phases_lived'] += phases_survived
                entry['phases_possible'] += total_phases
                
                if death:
                    if "Day 1" in death: entry['d1_lynches'] += 1
                    if "Night 1" in death: entry['n1_deaths'] += 1
                
                cause = (p.get('death_cause') or "").lower()
                if "mafia" in cause: entry['death_type_mafia'] += 1
                elif "sk" in cause or "serial" in cause: entry['death_type_sk'] += 1
                elif "lynch" in cause: entry['death_type_lynch'] += 1

        analytics_rows = []
        for name, data in player_map.items():
            skill_data = stats_cog._calculate_skill_scores(data['id'], classic_games)
            win_rate = (data['wins'] / data['games'] * 100) if data['games'] > 0 else 0
            surv_rate = (data['phases_lived'] / data['phases_possible'] * 100) if data['phases_possible'] > 0 else 0

            # Headers: Player Name, Skill Score, P, E, U, Games, Win %, Surv %, N1, D1, D_Maf, D_SK, D_Lynch
            analytics_rows.append([
                name,
                f"{skill_data['final_score']:.2f}",
                f"{skill_data['persuasion_norm']:.2f}",
                f"{skill_data['elusiveness_norm']:.2f}",
                f"{skill_data['understanding_norm']:.2f}",
                data['games'],
                f"{win_rate:.1f}",
                f"{surv_rate:.1f}",
                data['n1_deaths'],
                data['d1_lynches'],
                data['death_type_mafia'],
                data['death_type_sk'],
                data['death_type_lynch']
            ])
        
        # Sort by Skill Score Descending
        analytics_rows.sort(key=lambda x: float(x[1]), reverse=True)
        return analytics_rows

    async def run_export_logic(self):
        """
        The core logic, separated so it can be called by a command OR automatically.
        Returns a status string.
        """
        if not self.client:
            return "❌ Google Client not authenticated."

        stats_cog = self.bot.get_cog("StatsCog")
        if not stats_cog:
            return "❌ StatsCog not loaded."

        # 1. Load Data
        games_by_mode = stats_cog._load_and_group_games()
        # Flatten all games for the standard tabs (Classic + BR + etc)
        all_games = []
        for mode in games_by_mode:
            all_games.extend(games_by_mode[mode])
        
        # Get only classic for analytics
        classic_games = games_by_mode.get('classic', [])

        if not all_games:
            return "⚠️ No game data found to export."

        # 2. Compile Data
        games_rows, players_rows, votes_rows = self._compile_standard_data(all_games)
        analytics_rows = self._compile_analytics_data(classic_games, stats_cog)

        # 3. Upload to Google Sheets
        try:
            sheet = self._connect_to_sheet()
            
            # A. Update Standard Tabs
            await self._update_tab(sheet, "Games", [
                "Game_ID", "Game_Type", "Start_Time_UTC", "End_Time_UTC", "Total_Phases", "Winning_Faction"
            ], games_rows)
            
            await self._update_tab(sheet, "Players", [
                "Game_ID", "Player_ID", "Player_Name", "Role", "Alignment", "Is_Winner", "Death_Phase", "Death_Cause"
            ], players_rows)
            
            await self._update_tab(sheet, "Votes", [
                "Game_ID", "Phase", "Voter_ID", "Voter_Name", "Target_ID", "Target_Name"
            ], votes_rows)

            # B. Update New Analytics Tab
            await self._update_tab(sheet, "Analytics", [
                "Player Name", "Skill Score", "Persuasion (P)", "Elusiveness (E)", "Understanding (U)",
                "Games Played", "Win Rate %", "Survival %", "N1 Deaths", "D1 Lynches",
                "Deaths by Mafia", "Deaths by SK", "Times Lynched"
            ], analytics_rows)

            return f"✅ Success! Updated Games ({len(games_rows)}), Players ({len(players_rows)}), Votes ({len(votes_rows)}), and Analytics ({len(analytics_rows)})."

        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            raise e

    async def _update_tab(self, spreadsheet, tab_name, headers, data):
        """Helper to clear and replace a specific tab."""
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows=100, cols=20)
        
        worksheet.clear()
        if data:
            # Prepend headers
            all_rows = [headers] + data
            worksheet.update(range_name='A1', values=all_rows)
        else:
            worksheet.append_row(headers)

    @app_commands.command(name="exportstats", description="Force updates the Google Sheet with latest stats.")
    async def exportstats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            result = await self.run_export_logic()
            await interaction.followup.send(result, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Critical Export Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ExportCog(bot))