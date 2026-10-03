# game/actions/__init__.py
"""
Game actions package.
Re-exports individual action handlers from game.actions.*.
"""

from game.actions.block import handle_block
from game.actions.heal import handle_heal
from game.actions.kill import handle_kill
from game.actions.investigate import handle_investigation

ACTION_HANDLERS = {
    'block': handle_block,
    'kill': handle_kill,
    'heal': handle_heal,
    'investigate': handle_investigation,
}

__all__ = [
    "handle_block",
    "handle_heal",
    "handle_kill",
    "handle_investigation",
    "ACTION_HANDLERS",
]

