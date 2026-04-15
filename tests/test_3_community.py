import pytest
import json
from unittest.mock import patch, mock_open
import os

# Import the logic from your new package
from community.quirk_logic import save_approved_quirk, get_all_quirks, DATA_PATH

def test_get_all_quirks_file_missing():
    """Ensure it returns an empty dict if the file doesn't exist."""
    with patch("os.path.exists", return_value=False):
        assert get_all_quirks() == {}

def test_get_all_quirks_success():
    """Ensure it correctly loads existing data."""
    mock_data = '{"123": "Likes tea"}'
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=mock_data)):
            result = get_all_quirks()
            assert result["123"] == "Likes tea"

def test_save_approved_quirk_new_file():
    """Test saving a quirk when the file doesn't exist yet."""
    user_id = 456
    quirk = "Always wears a top hat"
    
    # We mock exists as False, then catch the write call
    with patch("os.path.exists", return_value=False):
        m = mock_open()
        with patch("builtins.open", m):
            save_approved_quirk(user_id, quirk)
            
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
            save_approved_quirk(user_id, long_quirk)
            
            handle = m()
            written_data = "".join(call.args[0] for call in handle.write.call_args_list)
            data = json.loads(written_data)
            assert len(data["789"]) == 100