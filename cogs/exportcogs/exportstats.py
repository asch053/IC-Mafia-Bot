# cogs/exportcogs/exportstats.py
import logging
import asyncio
import discord
import gspread
import config
from cogs.exportcogs.compiler import compile_standard_data, compile_analytics_data, compile_rules_data
from cogs.exportcogs.sheets_client import RULES_SHEET_HEADERS

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

try:
    from scripts.sync_google_sheets import sync_all_to_sheets
except ImportError:
    sync_all_to_sheets = None


async def run_export_logic(self, channel: discord.TextChannel = None, game_mode: str = None):
    """
    The Master Trigger: Called manually (/exportstats) or automatically by the Game Engine.
    Syncs the multi-era database (Forum, Discourse, Discord Bot, Discord Manual) to Google Sheets,
    updates the Rules Setup tab, and refreshes champion Discord roles.
    """
    if not self.client:
        return "❌ Google Client not authenticated."

    # 1. Multi-Era Google Sheets sync across all databases and analytics
    if sync_all_to_sheets:
        try:
            logger.info("Executing multi-era Google Sheets synchronization...")
            await asyncio.to_thread(sync_all_to_sheets)
            logger.info("Multi-era Google Sheets synchronization complete.")
        except Exception as e:
            logger.error(f"Multi-era Google Sheets sync encountered an error: {e}", exc_info=True)

    # 2. Sync Rules Setup tab for finished games
    stats_cog = self.bot.get_cog("StatsCog")
    all_games = []
    if stats_cog:
        games_by_mode = stats_cog._load_and_group_games()
        for mode in games_by_mode:
            all_games.extend(games_by_mode[mode])

    if all_games:
        try:
            sheet = self._connect_to_sheet()
            rules_tab_name = getattr(config, 'GOOGLE_SHEET_RULES_TAB', 'Rules Setup')
            try:
                ws_rules = sheet.worksheet(rules_tab_name)
            except gspread.WorksheetNotFound:
                ws_rules = sheet.add_worksheet(title=rules_tab_name, rows=100, cols=len(RULES_SHEET_HEADERS))
                ws_rules.append_row(RULES_SHEET_HEADERS)

            existing_rules_vals = ws_rules.get_all_values()
            if not existing_rules_vals:
                ws_rules.append_row(RULES_SHEET_HEADERS)
                existing_rules_vals = [RULES_SHEET_HEADERS]

            existing_gids = set(r[0] for r in existing_rules_vals[1:] if r)
            rules_rows = compile_rules_data(all_games)
            new_rules_rows = [r for r in rules_rows if r[0] not in existing_gids]
            if new_rules_rows:
                ws_rules.append_rows(new_rules_rows)
                logger.info(f"Appended {len(new_rules_rows)} missing game rules setups to '{rules_tab_name}'.")
        except Exception as e:
            logger.warning(f"Could not sync Rules Setup tab during export: {e}")

    # 3. Trigger Discord Champion Role Updates
    if self.bot and hasattr(self.bot, 'guilds') and self.bot.guilds:
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

    return "✅ Export & Multi-Era Sync Complete: Google Sheets and champion roles updated."


async def handle_export_stats(self, interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        result = await self.run_export_logic()
        await interaction.followup.send(result, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Critical Export Error: {e}", ephemeral=True)
