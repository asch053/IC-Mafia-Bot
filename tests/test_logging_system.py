# tests/test_logging_system.py
"""
Unit tests for the logging system overhaul:
1. DiscordCriticalHandler routes logging.CRITICAL events to the mod channel (config.MOD_CHANNEL_ID).
2. Lower severity levels (DEBUG, INFO, WARNING, ERROR) are not posted to Discord.
3. Rapid repeated critical errors are deduplicated/rate-limited by the handler.
4. Game engine critical points (game_loop_iteration, signup_loop, prepare_game) log CRITICAL upon unhandled errors.
"""
import unittest
import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock, patch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_0_logging import setup_test_logging
setup_test_logging()

import config
import setup.loggersetup as loggersetup
from setup.loggersetup import DiscordCriticalHandler
from game.engine.loop import game_loop_iteration
from game.engine.signup import signup_loop
from game.engine.prepare import prepare_game
from datetime import datetime, timezone, timedelta


class TestDiscordCriticalHandler(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.mock_channel = AsyncMock()
        self.mock_channel.send = AsyncMock()
        
        self.mock_bot = MagicMock()
        self.mock_bot.get_channel.return_value = self.mock_channel
        self.mock_bot.loop = asyncio.get_running_loop()
        
        # Reset recent alerts cache
        DiscordCriticalHandler._recent_alerts.clear()
        DiscordCriticalHandler.set_bot(self.mock_bot)

        self.handler = DiscordCriticalHandler(cooldown_seconds=10.0)
        self.test_logger = logging.getLogger("test_critical_logger")
        self.test_logger.setLevel(logging.DEBUG)
        self.test_logger.handlers.clear()
        self.test_logger.addHandler(self.handler)
        self.test_logger.propagate = False

    async def asyncTearDown(self):
        self.test_logger.removeHandler(self.handler)
        DiscordCriticalHandler.set_bot(None)

    async def test_critical_log_dispatches_embed(self):
        """CRITICAL logs should immediately dispatch a red embed to the mod channel."""
        self.test_logger.critical("Fatal: Phase failed to advance")
        await asyncio.sleep(0.05)  # Let scheduled task run

        self.mock_channel.send.assert_called_once()
        _, kwargs = self.mock_channel.send.call_args
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)
        self.assertIn("CRITICAL", embed.title)
        self.assertIn("Fatal: Phase failed to advance", embed.description)

    async def test_critical_log_with_exc_info_includes_traceback(self):
        """CRITICAL logs with exc_info should format and attach the traceback."""
        try:
            raise RuntimeError("Database connection timed out during phase loop")
        except RuntimeError:
            self.test_logger.critical("Game loop failed", exc_info=True)

        await asyncio.sleep(0.05)
        self.mock_channel.send.assert_called_once()
        _, kwargs = self.mock_channel.send.call_args
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)
        
        # Find the traceback field
        tb_field = next((f for f in embed.fields if f.name == "Traceback"), None)
        self.assertIsNotNone(tb_field)
        self.assertIn("RuntimeError", tb_field.value)
        self.assertIn("Database connection timed out", tb_field.value)

    async def test_lower_severity_levels_do_not_dispatch(self):
        """DEBUG, INFO, WARNING, and ERROR must NOT trigger Discord mod channel alerts."""
        self.test_logger.debug("System debug step")
        self.test_logger.info("Process milestone")
        self.test_logger.warning("Minor non-fatal warning")
        self.test_logger.error("Standard recoverable error")
        await asyncio.sleep(0.05)

        self.mock_channel.send.assert_not_called()

    async def test_deduplication_rate_limits_repeated_critical_errors(self):
        """Identical critical errors within the cooldown window should not spam Discord."""
        self.test_logger.critical("Repeated phase advancement stall")
        await asyncio.sleep(0.05)
        self.assertEqual(self.mock_channel.send.call_count, 1)

        # Emit the exact same log immediately
        self.test_logger.critical("Repeated phase advancement stall")
        await asyncio.sleep(0.05)
        # Should still be 1 (suppressed by cooldown)
        self.assertEqual(self.mock_channel.send.call_count, 1)

    async def test_missing_channel_handled_gracefully(self):
        """If mod channel does not exist, handler should not crash."""
        self.mock_bot.get_channel.return_value = None
        self.mock_bot.fetch_channel = AsyncMock(side_effect=Exception("Channel not found"))

        # Should complete without raising
        self.test_logger.critical("Error with no channel")
        await asyncio.sleep(0.05)


class TestGameEngineCriticalLogging(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        self.mock_role = MagicMock()
        self.mock_guild.get_role.return_value = self.mock_role

        self.mock_channel = AsyncMock()
        self.mock_channel.send = AsyncMock()
        self.mock_bot.get_channel.return_value = self.mock_channel
        self.mock_bot.fetch_channel = AsyncMock(return_value=self.mock_channel)

        self.mock_game = MagicMock()
        self.mock_game.bot = self.mock_bot
        self.mock_game.guild = self.mock_guild
        self.mock_game.players = {i: MagicMock(is_alive=True, display_name=f"Player{i}") for i in range(5)}
        self.mock_game._resolve_night_deaths = AsyncMock()
        self.mock_game.tally_votes = AsyncMock()
        self.mock_game.check_win_conditions = MagicMock(return_value=None)
        self.mock_game.get_status_message = MagicMock(return_value="Status OK")
        self.mock_game.role_status_message = AsyncMock(return_value="Role Status OK")
        self.mock_game.narration_manager = MagicMock()
        self.mock_game.narration_manager.construct_story = AsyncMock(return_value=None)
        self.mock_game.night_actions = {}
        self.mock_game.lynch_votes = {}
        self.mock_game.game_settings = {
            "current_phase": "night",
            "phase_number": 1,
            "phase_hours": 24,
            "phase_end_time": datetime.now(timezone.utc) - timedelta(seconds=10),
            "game_type": "classic"
        }
        self.mock_game.reminders_sent = set()

    @patch("game.engine.loop.logger.critical")
    async def test_game_loop_logs_critical_on_unhandled_phase_error(self, mock_critical):
        """When an unhandled exception occurs while advancing the phase, logger.critical must be invoked."""
        self.mock_game.process_night_actions = AsyncMock(side_effect=RuntimeError("Corrupted action state"))

        await game_loop_iteration(self.mock_game)

        mock_critical.assert_called_once()
        log_message = mock_critical.call_args[0][0]
        self.assertIn("failed to advance", log_message)
        self.assertIn("Corrupted action state", log_message)

    @patch("game.engine.signup.logger.critical")
    async def test_signup_loop_logs_critical_on_unhandled_error(self, mock_critical):
        """When signup_loop fails unexpectedly, logger.critical must be invoked."""
        self.mock_game.game_settings["current_phase"] = "signup"
        self.mock_game.game_settings["phase_end_time"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.mock_game.max_players = 10
        self.mock_game.prepare_game = AsyncMock(side_effect=RuntimeError("Setup crashed"))

        await signup_loop(self.mock_game)

        mock_critical.assert_called_once()
        log_message = mock_critical.call_args[0][0]
        self.assertIn("Sign-up loop encountered a critical error", log_message)

    @patch("game.engine.prepare.logger.critical")
    async def test_prepare_game_logs_critical_on_role_failure(self, mock_critical):
        """When roles cannot be generated, logger.critical must be invoked."""
        self.mock_game.game_settings["current_phase"] = "signup"
        self.mock_game.game_roles = []
        self.mock_game.reset = AsyncMock()

        with patch("game.engine.prepare.generate_game_roles"):
            self.mock_game.game_roles = []  # Empty roles
            await prepare_game(self.mock_game)

        mock_critical.assert_called()
        any_role_msg = any("Could not generate roles" in str(c[0][0]) for c in mock_critical.call_args_list)
        self.assertTrue(any_role_msg)


if __name__ == '__main__':
    unittest.main()
