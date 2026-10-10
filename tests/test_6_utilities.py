import unittest
import sys
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_0_logging import setup_test_logging
logger = setup_test_logging()

from utils.utilities import format_time_remaining, get_role_hierarchy

class TestUtilities(unittest.TestCase):
    logger.info(f"--- Starting Test Suite: {__name__} ---")
    def test_format_time_remaining_with_timedelta(self):
        msg = f"[START] {self._testMethodName} - Testing time format with duration"
        print(f"\n{msg}"); logger.info(msg)
        
        delta = timedelta(hours=2, minutes=30, seconds=15)
        
        action_msg = "[ACTION] Calling format_time_remaining"
        print(action_msg); logger.info(action_msg)
        
        result = format_time_remaining(delta)
        
        self.assertEqual(result, "2h 30m 15s")
        
        outcome_msg = f"[OUTCOME] Success! Duration formatted correctly: {result}"
        print(outcome_msg); logger.info(outcome_msg)

    def test_get_role_hierarchy_success(self):
        msg = f"[START] {self._testMethodName} - Testing role permissions"
        print(f"\n{msg}"); logger.info(msg)
        
        bot_role = MagicMock(position=10)
        target_role_1 = MagicMock(position=5)
        target_role_2 = MagicMock(position=8)
        
        action_msg = "[ACTION] Validating if bot (pos 10) outranks targets (pos 5, 8)"
        print(action_msg); logger.info(action_msg)
        
        result = get_role_hierarchy([target_role_1, target_role_2], bot_role)
        
        self.assertTrue(result)
        
        outcome_msg = f"[OUTCOME] Success! Bot correctly recognized as higher hierarchy."
        print(outcome_msg); logger.info(outcome_msg)


class TestChunkedMessage(unittest.IsolatedAsyncioTestCase):
    async def test_send_chunked_message_splits_on_newline(self):
        from utils.sendchunkedmessage import send_chunked_message
        from unittest.mock import AsyncMock

        mock_bot = MagicMock()
        mock_channel = AsyncMock()

        # Build a message with paragraphs
        line1 = "Paragraph 1: " + ("A" * 80)
        line2 = "Paragraph 2: " + ("B" * 80)
        full_text = f"{line1}\n{line2}"

        # Chunk size is smaller than the combined text but larger than line1
        chunk_size = 100
        await send_chunked_message(mock_bot, mock_channel, full_text, chunk_size=chunk_size)

        # Should split across 2 channel.send calls cleanly without cutting across words
        self.assertEqual(mock_channel.send.call_count, 2)
        sent_chunks = [call.args[0] for call in mock_channel.send.call_args_list]
        self.assertEqual(sent_chunks[0], line1)
        self.assertEqual(sent_chunks[1], line2)