# cogs/exportcogs/exportstats.py
import logging
import discord
import gspread
from cogs.exportcogs.compiler import compile_standard_data, compile_analytics_data

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def run_export_logic(self, channel: discord.TextChannel = None, game_mode: str = None):
    """
    The Master Trigger: Called manually or by the Game Engine.
    """
    if not self.client:
        return "❌ Google Client not authenticated."

    stats_cog = self.bot.get_cog("StatsCog")
    if not stats_cog:
        return "❌ StatsCog not loaded. Cannot calculate scores."

    games_by_mode = stats_cog._load_and_group_games()
    all_games = []
    for mode in games_by_mode:
        all_games.extend(games_by_mode[mode])

    classic_games = games_by_mode.get('classic', [])
    if not all_games:
        return "⚠️ No game data found to export."

    games_rows, players_rows, votes_rows = compile_standard_data(all_games)
    analytics_rows = compile_analytics_data(classic_games, stats_cog)

    try:
        sheet = self._connect_to_sheet()

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
            "Player ID", "Player Name", "Skill Score", "Persuasion (P)", "Elusiveness (E)", "Understanding (U)",
            "Games Played", "Games Won", "Phases Lived", "Phases Possible",
            "Win Rate %", "Survival %", "N1 Deaths", "D1 Lynches",
            "Deaths by Mafia", "Deaths by SK", "Times Lynched",
            "Vote Accuracy %", "Most Common Faction", "Best Role",
            "Losses", "Town Games", "Mafia Games", "Neutral/SK Games", "Plain Town Games",
            "Town Wins", "Mafia Wins", "Neutral/SK Wins", "Total Night Deaths"
        ], analytics_rows)

        if self.bot.guilds:
            main_guild = self.bot.guilds[0]
            fame_cog = self.bot.get_cog("FameCog")
            if fame_cog:
                logger.info("Triggering background role updates...")
                if game_mode in ["classic", "battle_royale"]:
                    await fame_cog.update_champion_roles(main_guild, mode=game_mode)
                else:
                    await fame_cog.update_champion_roles(main_guild, mode="classic")
                    await fame_cog.update_champion_roles(main_guild, mode="battle_royale")
            else:
                logger.warning("FameCog not found. Could not auto-update roles.")

        return f"✅ Export & Role Updates Complete: {len(games_rows)} games processed."

    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        raise e


async def handle_export_stats(self, interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        result = await self.run_export_logic()
        await interaction.followup.send(result, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Critical Export Error: {e}", ephemeral=True)

