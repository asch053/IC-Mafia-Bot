# utils/utilities.py
"""
Utilities facade module.
Re-exports individual single-responsibility utility functions for backward compatibility.
"""

from utils.loaddata import load_data
from utils.savejsondata import save_json_data
from utils.updatediscordroles import update_player_discord_roles
from utils.getrolehierarchy import get_role_hierarchy
from utils.formattimeremain import format_time_remaining
from utils.sendchunkedmessage import send_chunked_message
from utils.addchunkedfield import add_chunked_field
from utils.sendroledm import send_role_dm
from utils.sendmafiainfodm import send_mafia_info_dm
from utils.logprompttojson import log_prompt_to_json
from utils.archivephasedata import archive_phase_data
from utils.filtergamesbytime import filter_games_by_time

# Alias for compatibility if referenced as update_discord_roles
update_discord_roles = update_player_discord_roles

__all__ = [
    "load_data",
    "save_json_data",
    "update_player_discord_roles",
    "update_discord_roles",
    "get_role_hierarchy",
    "format_time_remaining",
    "send_chunked_message",
    "add_chunked_field",
    "send_role_dm",
    "send_mafia_info_dm",
    "log_prompt_to_json",
    "archive_phase_data",
    "filter_games_by_time",
]

