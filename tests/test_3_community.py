import pytest
import json
from unittest.mock import patch, mock_open
import os

# 1. MUST BE FIRST: Load logger & environment mocks
from tests.test_0_logging import setup_test_logging
logger = setup_test_logging()

# Import the logic from your new package
from community.quirk_logic import approve_quirk_logic, get_all_approved, get_all_pending, reject_quirk_logic, DATA_PATH

logger.info(f"--- Starting Test Suite: {__name__} ---")
def test_get_all_approved_file_missing():
    """Ensure it returns an empty dict if the file doesn't exist."""
    with patch("os.path.exists", return_value=False):
        assert get_all_approved() == {}

def test_get_all_approved_success():
    """Ensure it correctly loads existing data."""
    mock_data = '{"123": "Likes tea"}'
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=mock_data)):
            result = get_all_approved()
            assert result["123"] == "Likes tea"

def test_approve_quirk():
    """Test approving a quirk."""
    user_id = 456
    quirk = "Always wears a top hat"
    
    # We mock exists as False, then catch the write call
    with patch("os.path.exists", return_value=False):
        m = mock_open()
        with patch("builtins.open", m):
            approve_quirk_logic(user_id, quirk)

            handle = m()
            written_data = "".join(call.args[0] for call in handle.write.call_args_list)
            data = json.loads(written_data)
            assert data["456"] == quirk
        with patch("builtins.open", m):
            approve_quirk_logic(user_id)
            # Verify the file was opened for writing
            m.assert_called_once_with(DATA_PATH, 'w')
            
            # Check what was actually 'written' to the mock file
            handle = m()
            # Capture all calls to write() and join them
            written_data = "".join(call.args[0] for call in handle.write.call_args_list)
            data = json.loads(written_data)
            assert data["456"] == quirk

def test_quirk_truncation():
    """Ensure quirks longer than 100 characters are safely clipped."""
    long_quirk = "A" * 150
    user_id = 789
    
    with patch("os.path.exists", return_value=False):
        m = mock_open()
        with patch("builtins.open", m):
            approve_quirk_logic(user_id, long_quirk)
            
            handle = m()
            written_data = "".join(call.args[0] for call in handle.write.call_args_list)
            data = json.loads(written_data)
            assert len(data["789"]) == 100