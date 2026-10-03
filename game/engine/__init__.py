# game/engine/__init__.py
import logging
import discord
from discord.ext import tasks
import config
from utils.utilities import update_player_discord_roles

from . import (
    initialise,
    start,
    signup,
    prepare,
    voting,
    night,
    win,
    status,
    reset,
    persistence,
    loop
)

logger = logging.getLogger('discord')


class Game:
    """Manages the entire state and lifecycle of a single Mafia game."""

    def __init__(self, bot, guild, cleanup_callback=None, game_type="classic"):
        initialise.initialize_game(self, bot, guild, cleanup_callback, game_type)

    # --- LOOPS ---
    @tasks.loop(seconds=getattr(config, 'signup_loop_interval_seconds', 60))
    async def signup_loop(self):
        await signup.signup_loop(self)

    @signup_loop.before_loop
    async def before_signup_loop(self):
        await loop.before_signup_loop(self)

    @tasks.loop(seconds=getattr(config, 'game_loop_interval_seconds', 15))
    async def game_loop(self):
        await loop.game_loop_iteration(self)

    @game_loop.before_loop
    async def before_game_loop(self):
        await loop.before_game_loop(self)

    @game_loop.after_loop
    async def after_game_loop(self):
        await loop.after_game_loop(self)

    # --- START & SIGNUP ---
    async def start_game(self, *args, **kwargs):
        return await start.start_game(self, *args, **kwargs)

    async def start(self, *args, **kwargs):
        return await start.start_game(self, *args, **kwargs)

    async def force_start(self, interaction: discord.Interaction):
        return await signup.force_start(self, interaction)

    async def add_player(self, user, display_name: str, channel=None):
        return await signup.add_player(self, user, display_name, channel)

    async def remove_player(self, user, channel=None):
        return await signup.remove_player(self, user, channel)

    def add_npc(self, npc_name=None, channel=None):
        return signup.add_npc(self)

    # --- PREPARE & ROLES ---
    async def prepare_game(self):
        return await prepare.prepare_game(self)

    def generate_game_roles(self):
        return prepare.generate_game_roles(self)

    async def assign_roles(self):
        return await prepare.assign_roles(self)

    # --- VOTING ---
    async def process_lynch_vote(self, interaction: discord.Interaction, voter_user, target_name: str):
        return await voting.process_lynch_vote(self, interaction, voter_user, target_name)

    async def send_vote_count(self, channel=None):
        return await voting.send_vote_count(self, channel)

    async def tally_votes(self):
        return await voting.tally_votes(self)

    # --- NIGHT ACTIONS ---
    async def record_night_action(self, actor, action_type: str, target_name: str):
        return await night.record_night_action(self, actor, action_type, target_name)

    async def process_night_actions(self):
        return await night.process_night_actions(self)

    async def _resolve_night_deaths(self):
        return await night._resolve_night_deaths(self)

    def _handle_promotions(self, dead_player):
        return night._handle_promotions(self, dead_player)

    # --- WIN CONDITIONS & ENDING ---
    def check_win_conditions(self):
        return win.check_win_conditions(self)

    async def announce_winner(self, winner: str):
        return await win.announce_winner(self, winner)

    # --- STATUS & MESSAGES ---
    def get_player_by_name(self, name: str):
        return status.get_player_by_name(self, name)

    def get_status_message(self):
        return status.get_status_message(self)

    async def role_status_message(self):
        return await status.role_status_message(self)

    # --- RESET & PERSISTENCE ---
    async def reset(self):
        return await reset.reset(self)

    async def save_story_log(self, alignments, end_time):
        return await persistence.save_story_log(self, alignments, end_time)

    async def save_data_summary(self, game_data, final_summary):
        return await persistence.save_data_summary(self, game_data, final_summary)

    async def _save_game_summary(self, winner: str):
        return await persistence.save_game_summary(self, winner)

    async def export_game_stats(self):
        return await persistence.export_game_stats(self)

    # --- ADMIN CONTROLS ---
    async def force_end_phase(self, interaction: discord.Interaction):
        return await loop.force_end_phase(self, interaction)


__all__ = [
    'Game',
    'initialise',
    'start',
    'signup',
    'prepare',
    'voting',
    'night',
    'win',
    'status',
    'reset',
    'persistence',
    'loop',
    'update_player_discord_roles'
]

