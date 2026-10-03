import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tests.test_0_logging import setup_test_logging
logger = setup_test_logging()

import config
from cogs.exportcogs.sheets_client import (
    RULES_SHEET_HEADERS,
    log_game_setup_to_sheets_sync,
    log_game_setup_to_sheets
)
from cogs.exportcogs.compiler import compile_rules_data


class TestGoogleSheetsSetupLogging(unittest.TestCase):

    def test_rules_sheet_headers_defined(self):
        """Verify the 18 expected columns are present in RULES_SHEET_HEADERS."""
        expected = [
            "Game_ID", "Scheduled_At_UTC", "Scheduled_By", "Game_Type", "Story_Type",
            "Start_Time_UTC", "Phase_Hours", "Mafia_Ratio", "Town_Cop_Req", "Town_Doctor_Req",
            "Town_RB_Req", "Mafia_RB_Req", "SK_Player_Count", "GF_Investigatable", "SK_Investigatable",
            "GF_Night_Immune", "SK_Night_Immune", "BR_Skip_Day"
        ]
        self.assertEqual(RULES_SHEET_HEADERS, expected)

    @patch('cogs.exportcogs.sheets_client.get_sheets_client')
    @patch('cogs.exportcogs.sheets_client.connect_to_sheet')
    def test_log_game_setup_to_sheets_sync_append(self, mock_connect, mock_get_client):
        """Verify that a new game setup is appended when game_id is not already present."""
        mock_creds = MagicMock()
        mock_client = MagicMock()
        mock_get_client.return_value = (mock_creds, mock_client)

        mock_sheet = MagicMock()
        mock_connect.return_value = mock_sheet

        mock_ws = MagicMock()
        mock_sheet.worksheet.return_value = mock_ws
        # Existing values only have headers
        mock_ws.get_all_values.return_value = [RULES_SHEET_HEADERS]

        setup_data = {
            "game_id": "20261003-190000",
            "scheduled_at_utc": "2026-10-03T06:00:00Z",
            "scheduled_by": "TestAdmin",
            "game_type": "classic",
            "story_type": "Classic Mafia",
            "start_time_utc": "2026-10-04T12:00:00Z",
            "phase_hours": 12.0,
            "mafia_ratio": 0.25,
            "town_cop_req": 6,
            "town_doctor_req": 7,
            "town_rb_req": 10,
            "mafia_rb_req": 4,
            "sk_player_count": 9,
            "gf_investigate": False,
            "sk_investigate": True,
            "gf_night_immune": True,
            "sk_night_immune": False,
            "br_skip_day": False
        }

        success = log_game_setup_to_sheets_sync(setup_data)
        self.assertTrue(success)
        mock_ws.append_row.assert_called_once()
        appended_row = mock_ws.append_row.call_args[0][0]
        self.assertEqual(appended_row[0], "20261003-190000")
        self.assertEqual(appended_row[2], "TestAdmin")
        self.assertEqual(appended_row[3], "classic")
        self.assertEqual(appended_row[4], "Classic Mafia")
        self.assertEqual(appended_row[6], 12.0)
        self.assertEqual(appended_row[7], 0.25)
        self.assertEqual(appended_row[13], "No")
        self.assertEqual(appended_row[14], "Yes")
        self.assertEqual(appended_row[15], "Yes")
        self.assertEqual(appended_row[16], "No")
        self.assertEqual(appended_row[17], "No")

    @patch('cogs.exportcogs.sheets_client.get_sheets_client')
    @patch('cogs.exportcogs.sheets_client.connect_to_sheet')
    def test_log_game_setup_to_sheets_sync_update_existing(self, mock_connect, mock_get_client):
        """Verify that if a game_id already exists in the tab, it updates the existing row."""
        mock_creds = MagicMock()
        mock_client = MagicMock()
        mock_get_client.return_value = (mock_creds, mock_client)

        mock_sheet = MagicMock()
        mock_connect.return_value = mock_sheet

        mock_ws = MagicMock()
        mock_sheet.worksheet.return_value = mock_ws
        # Existing values include row 2 with same game_id
        mock_ws.get_all_values.return_value = [
            RULES_SHEET_HEADERS,
            ["20261003-190000", "old_time", "old_user", "classic", "Old Theme"]
        ]

        setup_data = {
            "game_id": "20261003-190000",
            "scheduled_at_utc": "2026-10-03T06:30:00Z",
            "scheduled_by": "NewAdmin",
            "game_type": "battle_royale",
            "story_type": "Cyberpunk",
            "start_time_utc": "2026-10-04T12:00:00Z",
            "phase_hours": 24.0,
            "mafia_ratio": 0.30,
            "town_cop_req": 5,
            "town_doctor_req": 5,
            "town_rb_req": 8,
            "mafia_rb_req": 3,
            "sk_player_count": 8,
            "gf_investigate": "yes",
            "sk_investigate": "no",
            "gf_night_immune": "no",
            "sk_night_immune": "yes",
            "br_skip_day": "yes"
        }

        success = log_game_setup_to_sheets_sync(setup_data)
        self.assertTrue(success)
        mock_ws.update.assert_called_once()
        self.assertEqual(mock_ws.update.call_args[1]['range_name'], "A2:R2")
        updated_row = mock_ws.update.call_args[1]['values'][0]
        self.assertEqual(updated_row[0], "20261003-190000")
        self.assertEqual(updated_row[2], "NewAdmin")
        self.assertEqual(updated_row[3], "battle_royale")
        self.assertEqual(updated_row[4], "Cyberpunk")
        self.assertEqual(updated_row[13], "Yes")
        self.assertEqual(updated_row[14], "No")
        self.assertEqual(updated_row[15], "No")
        self.assertEqual(updated_row[16], "Yes")
        self.assertEqual(updated_row[17], "Yes")

    def test_compile_rules_data(self):
        """Verify compiler.py properly extracts rule setups from games list."""
        games = [
            {
                "game_summary": {
                    "game_id": "20261001-120000",
                    "game_type": "classic",
                    "story_type": "High Fantasy",
                    "start_date_utc": "2026-10-01T12:00:00Z",
                    "phase_hours": 12,
                    "mafia_ratio": 0.25,
                    "town_cop_req": 6,
                    "town_doctor_req": 7,
                    "town_rb_req": 10,
                    "mafia_rb_req": 4,
                    "sk_player_count": 9,
                    "gf_investigate": False,
                    "sk_investigate": True,
                    "gf_night_immune": True,
                    "sk_night_immune": True,
                    "br_skip_day": True
                }
            }
        ]
        compiled = compile_rules_data(games)
        self.assertEqual(len(compiled), 1)
        row = compiled[0]
        self.assertEqual(row[0], "20261001-120000")
        self.assertEqual(row[3], "classic")
        self.assertEqual(row[4], "High Fantasy")
        self.assertEqual(row[13], "No")
        self.assertEqual(row[14], "Yes")
        self.assertEqual(row[15], "Yes")
        self.assertEqual(row[16], "Yes")
        self.assertEqual(row[17], "Yes")


class TestAsyncStartGameLogging(unittest.IsolatedAsyncioTestCase):

    @patch('cogs.exportcogs.sheets_client.log_game_setup_to_sheets')
    async def test_startgame_command_invokes_sheets_logging(self, mock_log_setup):
        """Verify that start_game_command calls log_game_setup_to_sheets."""
        from cogs.admincogs.startgame import start_game_command

        mock_cog = MagicMock()
        mock_cog.get_game_instance.return_value = None

        mock_interaction = MagicMock()
        mock_interaction.user.name = "CommanderAdmin"
        mock_interaction.user.mention = "@CommanderAdmin"
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()

        with patch('cogs.admincogs.startgame.Game') as mock_game_class:
            mock_game_instance = MagicMock()
            mock_game_instance.game_settings = {}
            mock_game_instance.start_game = AsyncMock()
            mock_game_class.return_value = mock_game_instance

            # Valid future time
            future_time = "2029-01-01 12:00"

            await start_game_command(
                self=mock_cog,
                interaction=mock_interaction,
                game_type="classic",
                phase_hours=12.0,
                start_datetime=future_time,
                narration_type="Classic Mafia",
                gf_investigate_choice="No",
                sk_investigate_choice="Yes",
                mafia_ratio=0.25,
                town_rb_req=10,
                mafia_rb_req=4,
                sk_player_count=9,
                town_cop_req=6,
                town_doctor_req=7,
                gf_night_immune_choice="Yes",
                sk_night_immune_choice="No",
                br_skip_day_choice="Yes"
            )

            mock_log_setup.assert_awaited_once()
            call_arg = mock_log_setup.call_args[0][0]
            self.assertEqual(call_arg["scheduled_by"], "CommanderAdmin")
            self.assertEqual(call_arg["game_type"], "classic")
            self.assertEqual(call_arg["story_type"], "Classic Mafia")
            self.assertEqual(call_arg["gf_investigate"], False)
            self.assertEqual(call_arg["sk_investigate"], True)
            self.assertEqual(call_arg["gf_night_immune"], True)
            self.assertEqual(call_arg["sk_night_immune"], False)
            self.assertEqual(call_arg["br_skip_day"], True)
            self.assertEqual(call_arg["phase_hours"], 12.0)


if __name__ == "__main__":
    unittest.main()
