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