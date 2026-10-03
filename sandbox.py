#!/usr/bin/env python3
"""
Game Logic Testbed & Sandbox for IC Mafia Bot.

Provides an isolated, Discord-free execution harness and interactive CLI to test,
debug, and simulate Mafia game logic, roles, voting, night actions, and win conditions.

Usage:
  Interactive CLI:
    python sandbox.py

  Run preset scenario:
    python sandbox.py --scenario doctor_saves_target
    python sandbox.py --scenario roleblock_prevents_kill
    python sandbox.py --scenario cop_investigates
    python sandbox.py --scenario jester_lynch
    python sandbox.py --scenario godfather_promotion
    python sandbox.py --scenario inactivity_death
    python sandbox.py --scenario town_victory
    python sandbox.py --scenario mafia_victory

  List available scenarios:
    python sandbox.py --list-scenarios

  Simulate full game:
    python sandbox.py --simulate --players 6
"""

import os
import sys
import asyncio
import logging
import random
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

# Ensure workspace root is in python path
WORKSPACE_ROOT = os.path.abspath(os.path.dirname(__file__))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

# Pre-populate environment variables so config.py loads cleanly without .env
ENV_DEFAULTS = {
    "BOT_TOKEN": "sandbox_mock_token",
    "SERVER_ID": "100000000000000001",
    "TALKY_TALKY_CHANNEL_ID": "100000000000000002",
    "STORIES_CHANNEL_ID": "100000000000000003",
    "VOTING_CHANNEL_ID": "100000000000000004",
    "RULES_AND_ROLES_CHANNEL_ID": "100000000000000005",
    "DEADZOR_CHANNEL_ID": "100000000000000006",
    "SIGN_UP_HERE_CHANNEL_ID": "100000000000000007",
    "MOD_CHANNEL_ID": "100000000000000008",
    "ANNOUNCEMENT_CHANNEL_ID": "100000000000000009",
    "LIVING_ROLE_ID": "200000000000000001",
    "DEAD_ROLE_ID": "200000000000000002",
    "MOD_ROLE_ID": "200000000000000003",
    "SPECTATOR_ROLE_ID": "200000000000000004",
    "CLASSIC_TOP_SKILL_ROLE_ID": "200000000000000005",
    "CLASSIC_TOP_SURVIVOR_ROLE_ID": "200000000000000006",
    "CLASSIC_RED_SHIRT_ROLE_ID": "200000000000000007",
    "BR_TOP_WINS_ROLE_ID": "200000000000000008",
    "BR_TOP_SURVIVOR_ROLE_ID": "200000000000000009",
    "BR_RED_SHIRT_ROLE_ID": "200000000000000010",
    "GOOGLE_SHEET_ID": "mock_sheet_id",
    "GOOGLE_CREDENTIALS_FILE": "mock_creds.json",
    "GOOGLE_SIMULATION_SHEET_ID": "mock_sim_sheet_id",
    "GOOGLE_AI_API_KEY": "mock_ai_key",
    "OWNER_ID": "999999999999999999",
    "GAME_TYPE": "Testing",
    "BOT_PREFIX": "/",
}
for k, v in ENV_DEFAULTS.items():
    os.environ.setdefault(k, v)

# Discord logger setup
logger = logging.getLogger("discord")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.WARNING)

import discord
import config
from game.engine import Game
from game.player import Player
from game.roles import get_role_instance, ALL_ROLES_DATA
from game import setup_generator


# ==============================================================================
# Mock Discord Entities
# ==============================================================================

class MockDiscordRole:
    """Mock Discord Role for living/dead/spectator tracking."""
    def __init__(self, role_id: int, name: str):
        self.id = role_id
        self.name = name
        self.mention = f"@{name}"

    def __repr__(self):
        return f"<MockRole id={self.id} name='{self.name}'>"


class MockDiscordChannel:
    """Mock Discord Channel that logs posted messages and embeds."""
    def __init__(self, channel_id: int, name: str):
        self.id = channel_id
        self.name = name
        self.messages: List[Dict[str, Any]] = []

    async def send(self, content: Optional[str] = None, embed: Optional[Any] = None, **kwargs) -> Any:
        msg_entry = {
            "channel_id": self.id,
            "channel_name": self.name,
            "content": content,
            "embed": embed,
            "timestamp": datetime.now(timezone.utc),
            "extra": kwargs
        }
        self.messages.append(msg_entry)
        return msg_entry

    def last_message(self) -> Optional[str]:
        if not self.messages:
            return None
        return self.messages[-1].get("content")


class MockDiscordUser:
    """Mock Discord User / Member capable of receiving DMs and tracking roles."""
    def __init__(self, user_id: int, name: str, display_name: Optional[str] = None):
        self.id = user_id
        self.name = name
        self.display_name = display_name or name
        self.roles: List[MockDiscordRole] = []
        self.dms: List[Dict[str, Any]] = []

    async def send(self, content: Optional[str] = None, embed: Optional[Any] = None, **kwargs) -> Any:
        dm_entry = {
            "user_id": self.id,
            "user_name": self.name,
            "content": content,
            "embed": embed,
            "timestamp": datetime.now(timezone.utc),
            "extra": kwargs
        }
        self.dms.append(dm_entry)
        return dm_entry

    async def add_roles(self, *roles: MockDiscordRole, **kwargs) -> None:
        for r in roles:
            if r not in self.roles:
                self.roles.append(r)

    async def remove_roles(self, *roles: MockDiscordRole, **kwargs) -> None:
        for r in roles:
            if r in self.roles:
                self.roles.remove(r)

    def last_dm(self) -> Optional[str]:
        if not self.dms:
            return None
        return self.dms[-1].get("content")


class MockDiscordGuild:
    """Mock Guild providing role and member lookup."""
    def __init__(self, guild_id: int = 100000000000000001, name: str = "Sandbox Guild"):
        self.id = guild_id
        self.name = name
        self.roles_by_id: Dict[int, MockDiscordRole] = {
            getattr(config, "LIVING_ROLE_ID", 200000000000000001): MockDiscordRole(getattr(config, "LIVING_ROLE_ID", 200000000000000001), "Living"),
            getattr(config, "DEAD_ROLE_ID", 200000000000000002): MockDiscordRole(getattr(config, "DEAD_ROLE_ID", 200000000000000002), "Dead"),
            getattr(config, "SPECTATOR_ROLE_ID", 200000000000000004): MockDiscordRole(getattr(config, "SPECTATOR_ROLE_ID", 200000000000000004), "Spectator"),
            getattr(config, "MOD_ROLE_ID", 200000000000000003): MockDiscordRole(getattr(config, "MOD_ROLE_ID", 200000000000000003), "Moderator"),
        }
        self.members: List[MockDiscordUser] = []

    def get_role(self, role_id: int) -> Optional[MockDiscordRole]:
        return self.roles_by_id.get(role_id)

    def get_member(self, user_id: int) -> Optional[MockDiscordUser]:
        for m in self.members:
            if m.id == user_id:
                return m
        return None

    def add_member(self, user: MockDiscordUser) -> None:
        if not any(m.id == user.id for m in self.members):
            self.members.append(user)


class MockDiscordBot:
    """Mock Bot client providing channel/user fetching and event stubs."""
    def __init__(self, guild: MockDiscordGuild):
        self.guild = guild
        self.channels_by_id: Dict[int, MockDiscordChannel] = {
            getattr(config, "TALKY_TALKY_CHANNEL_ID", 100000000000000002): MockDiscordChannel(getattr(config, "TALKY_TALKY_CHANNEL_ID", 100000000000000002), "talky-talky"),
            getattr(config, "STORIES_CHANNEL_ID", 100000000000000003): MockDiscordChannel(getattr(config, "STORIES_CHANNEL_ID", 100000000000000003), "stories"),
            getattr(config, "VOTING_CHANNEL_ID", 100000000000000004): MockDiscordChannel(getattr(config, "VOTING_CHANNEL_ID", 100000000000000004), "voting-channel"),
            getattr(config, "RULES_AND_ROLES_CHANNEL_ID", 100000000000000005): MockDiscordChannel(getattr(config, "RULES_AND_ROLES_CHANNEL_ID", 100000000000000005), "rules-and-roles"),
            getattr(config, "DEADZOR_CHANNEL_ID", 100000000000000006): MockDiscordChannel(getattr(config, "DEADZOR_CHANNEL_ID", 100000000000000006), "deadzor"),
            getattr(config, "SIGN_UP_HERE_CHANNEL_ID", 100000000000000007): MockDiscordChannel(getattr(config, "SIGN_UP_HERE_CHANNEL_ID", 100000000000000007), "sign-up-here"),
            getattr(config, "MOD_CHANNEL_ID", 100000000000000008): MockDiscordChannel(getattr(config, "MOD_CHANNEL_ID", 100000000000000008), "mod"),
            getattr(config, "ANNOUNCEMENT_CHANNEL_ID", 100000000000000009): MockDiscordChannel(getattr(config, "ANNOUNCEMENT_CHANNEL_ID", 100000000000000009), "announcement"),
        }
        self.users_by_id: Dict[int, MockDiscordUser] = {}
        self.cogs: Dict[str, Any] = {}

    def get_channel(self, channel_id: int) -> Optional[MockDiscordChannel]:
        return self.channels_by_id.get(channel_id)

    async def fetch_user(self, user_id: int) -> MockDiscordUser:
        if user_id not in self.users_by_id:
            user = MockDiscordUser(user_id, f"User_{user_id}")
            self.users_by_id[user_id] = user
            self.guild.add_member(user)
        return self.users_by_id[user_id]

    def get_cog(self, name: str) -> Optional[Any]:
        return self.cogs.get(name)

    async def wait_until_ready(self) -> None:
        pass


class MockInteraction:
    """Mock Discord Interaction for slash command simulation."""
    def __init__(self, user: MockDiscordUser):
        self.user = user
        self.response = MockInteractionResponse()

    async def followup(self, *args, **kwargs):
        pass


class MockInteractionResponse:
    def __init__(self):
        self.messages: List[str] = []

    async def send_message(self, message: str, **kwargs) -> None:
        self.messages.append(message)


# ==============================================================================
# Game Sandbox Testbed Controller
# ==============================================================================

class GameSandbox:
    """
    High-level testbed controller managing an isolated Mafia Game instance.
    Provides deterministic step-by-step game progression, voting, actions,
    and state inspection without Discord dependencies.
    """

    def __init__(self, game_type: str = "classic", player_names: Optional[List[str]] = None, num_npcs: int = 0):
        self.guild = MockDiscordGuild()
        self.bot = MockDiscordBot(self.guild)
        self.game_type = game_type
        self.game: Optional[Game] = None
        self._next_user_id = 1001

        self.initialize(game_type=game_type, player_names=player_names, num_npcs=num_npcs)

    def initialize(self, game_type: str = "classic", player_names: Optional[List[str]] = None, num_npcs: int = 0) -> None:
        """Sets up a fresh Game instance with mock Discord bindings."""
        self.game_type = game_type
        self.game = Game(bot=self.bot, guild=self.guild, game_type=game_type)
        self.game.game_settings["game_type"] = game_type
        self.game.game_settings["game_id"] = f"SANDBOX_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.game.game_settings["phase_end_time"] = datetime.now(timezone.utc) + timedelta(hours=12)

        # Ensure loops do not run in background threads during sandbox testing
        if hasattr(self.game, 'signup_loop') and hasattr(self.game.signup_loop, 'cancel'):
            self.game.signup_loop.cancel()
        if hasattr(self.game, 'game_loop') and hasattr(self.game.game_loop, 'cancel'):
            self.game.game_loop.cancel()

        if player_names:
            for name in player_names:
                self.add_player(name)

        for _ in range(num_npcs):
            self.add_npc()

    # --- Player Management ---

    def add_player(self, display_name: str, user_id: Optional[int] = None) -> Player:
        """Adds a human (mock) player to the sandbox."""
        if user_id is None:
            user_id = self._next_user_id
            self._next_user_id += 1

        mock_user = MockDiscordUser(user_id=user_id, name=display_name.lower().replace(" ", "_"), display_name=display_name)
        self.bot.users_by_id[user_id] = mock_user
        self.guild.add_member(mock_user)

        player = Player(user_id, mock_user.name, display_name)
        self.game.players[user_id] = player
        return player

    def add_npc(self, name: Optional[str] = None) -> Player:
        """Adds an NPC bot player."""
        npc_name = name or self.game.add_npc()
        if isinstance(npc_name, str):
            # add_npc in signup creates player with negative ID
            player = self.game.get_player_by_name(npc_name)
            if player:
                return player
        # Fallback manual NPC creation if name specified
        npc_id = -len([p for p in self.game.players.values() if p.is_npc]) - 1
        npc_display = name or f"Bot_{abs(npc_id)}"
        player = Player(npc_id, npc_display.lower(), npc_display)
        self.game.players[npc_id] = player
        return player

    def remove_player(self, name: str) -> bool:
        """Removes a player by display name."""
        player = self.get_player(name)
        if player and player.id in self.game.players:
            del self.game.players[player.id]
            return True
        return False

    def get_player(self, name: str) -> Optional[Player]:
        """Retrieves a player by display name (case-insensitive)."""
        return self.game.get_player_by_name(name)

    def set_player_role(self, player_name: str, role_name: str) -> bool:
        """Directly assigns a specific role (e.g. 'Town Doctor', 'Godfather') to a player."""
        player = self.get_player(player_name)
        if not player:
            return False
        role = get_role_instance(role_name)
        if not role:
            return False
        player.assign_role(role)
        return True

    def auto_assign_roles(self) -> List[str]:
        """Runs the game's dynamic role generator and assigns roles to current players."""
        self.game.generate_game_roles()
        # Synchronously assign generated roles without waiting for external Discord DMs
        role_pool = self.game.game_roles[:]
        random.shuffle(role_pool)
        for player_obj, role in zip(self.game.players.values(), role_pool):
            player_obj.assign_role(role)
        return [f"{p.display_name}: {p.role.name}" for p in self.game.players.values() if p.role]

    # --- Phase Progression ---

    def start_day(self, phase_number: Optional[int] = None) -> None:
        """Transitions sandbox into the Day phase."""
        if phase_number is not None:
            self.game.game_settings["phase_number"] = phase_number
        elif self.game.game_settings.get("current_phase") in ["setup", "preparation"]:
            self.game.game_settings["phase_number"] = 1

        self.game.game_settings["current_phase"] = "day"
        self.game.game_settings["phase_end_time"] = datetime.now(timezone.utc) + timedelta(hours=12)
        self.game.lynch_votes.clear()
        for p in self.game.players.values():
            p.action_target = None

    def start_night(self, phase_number: Optional[int] = None) -> None:
        """Transitions sandbox into the Night phase."""
        if phase_number is not None:
            self.game.game_settings["phase_number"] = phase_number
        elif self.game.game_settings.get("current_phase") == "day":
            self.game.game_settings["phase_number"] += 1
        elif self.game.game_settings.get("current_phase") in ["setup", "preparation"]:
            self.game.game_settings["phase_number"] = 1

        self.game.game_settings["current_phase"] = "night"
        self.game.game_settings["phase_end_time"] = datetime.now(timezone.utc) + timedelta(hours=12)
        self.game.night_actions.clear()
        self.game.heals_on_players.clear()
        self.game.kill_attempts_on.clear()
        self.game.blocked_players_this_night.clear()
        for p in self.game.players.values():
            p.action_target = None

    # --- Voting (Day Phase) ---

    async def cast_vote(self, voter_name: str, target_name: str) -> str:
        """Simulates a player casting a lynch vote for a target."""
        voter = self.get_player(voter_name)
        if not voter:
            return f"Error: Voter '{voter_name}' not found."

        mock_user = await self.bot.fetch_user(voter.id)
        mock_interaction = MockInteraction(mock_user)

        res = await self.game.process_lynch_vote(mock_interaction, mock_user, target_name)
        return res or "Vote recorded."

    def get_vote_tally(self) -> Dict[str, Any]:
        """Returns the current vote counts, candidate voters, and remaining voters."""
        tally = {}
        for target_id, voter_ids in self.game.lynch_votes.items():
            target = self.game.players.get(target_id)
            if target:
                voters = [self.game.players[vid].display_name for vid in voter_ids if vid in self.game.players]
                tally[target.display_name] = {
                    "count": len(voter_ids),
                    "voters": voters
                }

        living_players = [p for p in self.game.players.values() if p.is_alive]
        voted_ids = set()
        for v_list in self.game.lynch_votes.values():
            voted_ids.update(v_list)
        not_voted = [p.display_name for p in living_players if p.id not in voted_ids]

        return {
            "tally": tally,
            "not_voted": not_voted,
            "total_living": len(living_players)
        }

    async def resolve_day(self) -> Dict[str, Any]:
        """Tallies votes, applies lynch and inactivity deaths, and checks win conditions."""
        self.game.game_settings["current_phase"] = "pre-night"
        living_before = {p.id for p in self.game.players.values() if p.is_alive}

        winner = await self.game.tally_votes()
        if not winner:
            winner = self.game.check_win_conditions()

        # Allow any background scheduled tasks (such as DMs) to execute
        await asyncio.sleep(0.05)

        living_after = {p.id for p in self.game.players.values() if p.is_alive}
        deaths = [self.game.players[pid] for pid in (living_before - living_after)]

        return {
            "phase": f"Day {self.game.game_settings.get('phase_number')}",
            "deaths": deaths,
            "winner": winner
        }

    # --- Night Actions (Night Phase) ---

    async def record_action(self, actor_name: str, action_type: str, target_name: str) -> str:
        """Records a night action (kill, heal, block, investigate) for an actor on a target."""
        actor = self.get_player(actor_name)
        if not actor:
            return f"Error: Actor '{actor_name}' not found."

        res = await self.game.record_night_action(actor.id, action_type, target_name)
        return res

    def get_queued_actions(self) -> List[Dict[str, Any]]:
        """Returns the list of currently queued night actions."""
        res = []
        for actor_id, data in self.game.night_actions.items():
            actor = self.game.players.get(actor_id)
            target = self.game.players.get(data.get("target_id"))
            res.append({
                "actor": actor.display_name if actor else f"ID {actor_id}",
                "action": data.get("type"),
                "target": target.display_name if target else f"ID {data.get('target_id')}",
                "priority": data.get("night_priority")
            })
        return res

    async def resolve_night(self) -> Dict[str, Any]:
        """Resolves queued night actions in priority order, applies deaths, and checks win conditions."""
        self.game.game_settings["current_phase"] = "pre-day"
        living_before = {p.id for p in self.game.players.values() if p.is_alive}

        await self.game.process_night_actions()
        await self.game._resolve_night_deaths()

        # Update last_action_target_id
        processed = self.game.night_actions.copy()
        for p in self.game.players.values():
            if p.id not in processed:
                p.last_action_target_id = None
        for p_id, action_data in processed.items():
            if action_data.get('type') in ['heal', 'block']:
                act_player = self.game.players.get(p_id)
                if act_player:
                    act_player.last_action_target_id = action_data.get('target_id')

        # Allow background scheduled tasks (such as investigation and promotion DMs) to execute
        await asyncio.sleep(0.05)

        winner = self.game.check_win_conditions()
        living_after = {p.id for p in self.game.players.values() if p.is_alive}
        deaths = [self.game.players[pid] for pid in (living_before - living_after)]

        return {
            "phase": f"Night {self.game.game_settings.get('phase_number')}",
            "deaths": deaths,
            "blocked": list(self.game.blocked_players_this_night.keys()),
            "winner": winner
        }

    # --- Game State Inspection ---

    def check_win(self) -> Optional[str]:
        """Evaluates win conditions and returns the winner ('Town', 'Mafia', 'Serial Killer', 'Draw', etc.)."""
        return self.game.check_win_conditions()

    def get_status_overview(self) -> Dict[str, Any]:
        """Returns a structured summary of the current sandbox state."""
        living = [p for p in self.game.players.values() if p.is_alive]
        dead = [p for p in self.game.players.values() if not p.is_alive]
        return {
            "game_id": self.game.game_settings.get("game_id"),
            "game_type": self.game.game_settings.get("game_type"),
            "phase": self.game.game_settings.get("current_phase"),
            "phase_number": self.game.game_settings.get("phase_number"),
            "living_count": len(living),
            "dead_count": len(dead),
            "winner": self.check_win(),
            "living_players": [
                {
                    "name": p.display_name,
                    "role": p.role.name if p.role else "None",
                    "alignment": p.role.alignment if p.role else "None",
                    "is_npc": p.is_npc
                }
                for p in living
            ],
            "dead_players": [
                {
                    "name": p.display_name,
                    "role": p.role.name if p.role else "None",
                    "alignment": p.role.alignment if p.role else "None",
                    "death_info": p.death_info
                }
                for p in dead
            ]
        }

    def print_status(self) -> None:
        """Pretty-prints the game state to console."""
        info = self.get_status_overview()
        phase_str = f"{str(info['phase']).capitalize()} {info['phase_number']}"
        print(f"\n{'='*60}")
        print(f"  MAFIA SANDBOX STATUS: {info['game_id']}")
        print(f"  Phase: {phase_str} | Mode: {info['game_type']} | Winner: {info['winner'] or 'None'}")
        print(f"{'='*60}")

        print(f"\n[Living Players ({info['living_count']})]:")
        for lp in info["living_players"]:
            npc_tag = " [NPC]" if lp["is_npc"] else ""
            print(f"  - {lp['name']:<15} | Role: {lp['role']:<18} | Alignment: {lp['alignment']}{npc_tag}")

        if info["dead_players"]:
            print(f"\n[Dead Players ({info['dead_count']})]:")
            for dp in info["dead_players"]:
                cause = dp["death_info"].get("how", "Unknown")
                phase = dp["death_info"].get("phase", "Unknown")
                print(f"  - {dp['name']:<15} | Role: {dp['role']:<18} | Died: {phase} ({cause})")
        print(f"{'='*60}\n")


# ==============================================================================
# Preset Scenario Suite
# ==============================================================================

class ScenarioSuite:
    """Pre-built test scenarios for verifying core game logic rules."""

    @staticmethod
    async def doctor_saves_target() -> bool:
        """Scenario: Doctor heals a player targeted by Mafia -> Target survives."""
        print("\n--- [Scenario: Doctor Saves Target] ---")
        sb = GameSandbox(game_type="classic", player_names=["Alice", "Bob", "Charlie", "Dave"])
        sb.set_player_role("Alice", "Godfather")
        sb.set_player_role("Bob", "Town Doctor")
        sb.set_player_role("Charlie", "Plain Townie")
        sb.set_player_role("Dave", "Plain Townie")

        sb.start_night(1)
        # Mafia attacks Charlie, Doctor protects Charlie
        res_kill = await sb.record_action("Alice", "kill", "Charlie")
        res_heal = await sb.record_action("Bob", "heal", "Charlie")
        print(f"  Action 1: Alice -> {res_kill}")
        print(f"  Action 2: Bob   -> {res_heal}")

        night_res = await sb.resolve_night()
        print(f"  Night Deaths: {[p.display_name for p in night_res['deaths']]}")

        charlie = sb.get_player("Charlie")
        passed = charlie.is_alive and len(night_res["deaths"]) == 0
        print(f"  Outcome: {'PASS (Charlie survived)' if passed else 'FAIL'}")
        return passed

    @staticmethod
    async def roleblock_prevents_kill() -> bool:
        """Scenario: Town Role Blocker blocks Mafia Goon -> Kill prevented."""
        print("\n--- [Scenario: Roleblock Prevents Kill] ---")
        sb = GameSandbox(game_type="classic", player_names=["Goon", "Blocker", "Victim", "Innocent"])
        sb.set_player_role("Goon", "Mob Goon")
        sb.set_player_role("Blocker", "Town Role Blocker")
        sb.set_player_role("Victim", "Plain Townie")
        sb.set_player_role("Innocent", "Plain Townie")

        sb.start_night(1)
        await sb.record_action("Goon", "kill", "Victim")
        await sb.record_action("Blocker", "block", "Goon")

        night_res = await sb.resolve_night()
        victim = sb.get_player("Victim")
        passed = victim.is_alive and len(night_res["deaths"]) == 0
        print(f"  Deaths: {[p.display_name for p in night_res['deaths']]}")
        print(f"  Outcome: {'PASS (Goon blocked, victim lived)' if passed else 'FAIL'}")
        return passed

    @staticmethod
    async def cop_investigates() -> bool:
        """Scenario: Cop investigates Godfather (investigation immune) and Mob Goon (guilty)."""
        print("\n--- [Scenario: Cop Investigates] ---")
        sb = GameSandbox(game_type="classic", player_names=["Cop", "Godfather", "Goon", "Townie"])
        sb.set_player_role("Cop", "Town Cop")
        sb.set_player_role("Godfather", "Godfather")
        sb.set_player_role("Goon", "Mob Goon")
        sb.set_player_role("Townie", "Plain Townie")

        # Night 1: Cop investigates Godfather (immune -> returns innocent/Townie)
        sb.start_night(1)
        await sb.record_action("Cop", "investigate", "Godfather")
        await sb.resolve_night()

        cop_user = await sb.bot.fetch_user(sb.get_player("Cop").id)
        gf_report = cop_user.last_dm() or ""
        print(f"  Godfather Investigation DM: {gf_report.strip()}")

        # Night 2: Cop investigates Goon (not immune -> returns Mob Goon)
        sb.start_night(2)
        await sb.record_action("Cop", "investigate", "Goon")
        await sb.resolve_night()

        goon_report = cop_user.last_dm() or ""
        print(f"  Mob Goon Investigation DM: {goon_report.strip()}")

        passed = ("Plain Townie" in gf_report or "Town" in gf_report) and ("Mob Goon" in goon_report)
        print(f"  Outcome: {'PASS (Immunity & detection verified)' if passed else 'FAIL'}")
        return passed

    @staticmethod
    async def jester_lynch() -> bool:
        """Scenario: Jester is lynched during the Day phase -> Jester wins."""
        print("\n--- [Scenario: Jester Lynch] ---")
        sb = GameSandbox(game_type="classic", player_names=["JesterPlayer", "TownA", "TownB", "MafiaA"])
        sb.set_player_role("JesterPlayer", "Jester")
        sb.set_player_role("TownA", "Plain Townie")
        sb.set_player_role("TownB", "Plain Townie")
        sb.set_player_role("MafiaA", "Godfather")

        sb.start_day(1)
        await sb.cast_vote("TownA", "JesterPlayer")
        await sb.cast_vote("TownB", "JesterPlayer")
        await sb.cast_vote("MafiaA", "JesterPlayer")

        day_res = await sb.resolve_day()
        jester = sb.get_player("JesterPlayer")
        passed = (not jester.is_alive) and (day_res["winner"] == "Jester")
        print(f"  Lynched: {[p.display_name for p in day_res['deaths']]}")
        print(f"  Winner: {day_res['winner']}")
        print(f"  Outcome: {'PASS (Jester won upon lynch)' if passed else 'FAIL'}")
        return passed

    @staticmethod
    async def godfather_promotion() -> bool:
        """Scenario: Godfather dies, surviving Mob Goon is promoted to killer."""
        print("\n--- [Scenario: Godfather Promotion] ---")
        sb = GameSandbox(game_type="classic", player_names=["GF", "Goon", "TownieA", "TownieB"])
        sb.set_player_role("GF", "Godfather")
        sb.set_player_role("Goon", "Mob Goon")
        sb.set_player_role("TownieA", "Plain Townie")
        sb.set_player_role("TownieB", "Plain Townie")

        goon = sb.get_player("Goon")
        initial_kill_ability = "kill" in (goon.role.abilities or {})

        # Town lynches Godfather
        sb.start_day(1)
        await sb.cast_vote("TownieA", "GF")
        await sb.cast_vote("TownieB", "GF")
        await sb.cast_vote("Goon", "GF")
        await sb.resolve_day()

        post_promotion_kill = "kill" in (goon.role.abilities or {})
        passed = (not initial_kill_ability) and post_promotion_kill
        print(f"  Initial Goon has kill: {initial_kill_ability}")
        print(f"  After GF death, Goon has kill: {post_promotion_kill}")
        print(f"  Outcome: {'PASS (Mob Goon promoted)' if passed else 'FAIL'}")
        return passed

    @staticmethod
    async def inactivity_death() -> bool:
        """Scenario: Player misses votes across days -> eliminated for inactivity."""
        print("\n--- [Scenario: Inactivity Elimination] ---")
        sb = GameSandbox(game_type="classic", player_names=["Active1", "Active2", "Slacker", "Mafia1"])
        sb.set_player_role("Active1", "Plain Townie")
        sb.set_player_role("Active2", "Plain Townie")
        sb.set_player_role("Slacker", "Plain Townie")
        sb.set_player_role("Mafia1", "Godfather")

        max_missed = getattr(config, "MAX_MISSED_VOTES", 2)
        if not isinstance(max_missed, int):
            max_missed = 2
        slacker = sb.get_player("Slacker")

        for d in range(1, max_missed + 2):
            if not slacker.is_alive:
                break
            sb.start_day(d)
            # Active players vote for each other (tie so neither is lynched)
            await sb.cast_vote("Active1", "Active2")
            await sb.cast_vote("Active2", "Active1")
            # Slacker does not vote!
            await sb.resolve_day()

        passed = not slacker.is_alive and slacker.death_info.get("how") == "Inactivity"
        print(f"  Slacker status: Alive={slacker.is_alive}, Death={slacker.death_info}")
        print(f"  Outcome: {'PASS (Inactivity modkill applied)' if passed else 'FAIL'}")
        return passed

    @staticmethod
    async def town_victory() -> bool:
        """Scenario: All Mafia eliminated -> Town wins."""
        print("\n--- [Scenario: Town Victory] ---")
        sb = GameSandbox(game_type="classic", player_names=["Cop", "Doctor", "Townie", "Goon"])
        sb.set_player_role("Cop", "Town Cop")
        sb.set_player_role("Doctor", "Town Doctor")
        sb.set_player_role("Townie", "Plain Townie")
        sb.set_player_role("Goon", "Mob Goon")

        sb.start_day(1)
        await sb.cast_vote("Cop", "Goon")
        await sb.cast_vote("Doctor", "Goon")
        await sb.cast_vote("Townie", "Goon")
        day_res = await sb.resolve_day()

        passed = day_res["winner"] == "Town"
        print(f"  Winner: {day_res['winner']}")
        print(f"  Outcome: {'PASS (Town declared winner)' if passed else 'FAIL'}")
        return passed

    @staticmethod
    async def mafia_victory() -> bool:
        """Scenario: Mafia equals or outnumbers Town -> Mafia wins."""
        print("\n--- [Scenario: Mafia Victory] ---")
        sb = GameSandbox(game_type="classic", player_names=["Goon", "TownieA"])
        sb.set_player_role("Goon", "Mob Goon")
        sb.set_player_role("TownieA", "Plain Townie")

        sb.start_night(1)
        winner = sb.check_win()
        passed = (winner == "Mafia")
        print(f"  Winner: {winner}")
        print(f"  Outcome: {'PASS (Mafia declared winner on parity)' if passed else 'FAIL'}")
        return passed


SCENARIOS = {
    "doctor_saves_target": ScenarioSuite.doctor_saves_target,
    "roleblock_prevents_kill": ScenarioSuite.roleblock_prevents_kill,
    "cop_investigates": ScenarioSuite.cop_investigates,
    "jester_lynch": ScenarioSuite.jester_lynch,
    "godfather_promotion": ScenarioSuite.godfather_promotion,
    "inactivity_death": ScenarioSuite.inactivity_death,
    "town_victory": ScenarioSuite.town_victory,
    "mafia_victory": ScenarioSuite.mafia_victory,
}


# ==============================================================================
# Automated Full Game Simulation
# ==============================================================================

async def run_full_simulation(num_players: int = 6, game_type: str = "classic", max_rounds: int = 15) -> Optional[str]:
    """Simulates a full automated game from start to finish with heuristic voting/actions."""
    print(f"\n{'*'*60}")
    print(f"  RUNNING FULL MAFIA SIMULATION ({num_players} Players, Mode: {game_type})")
    print(f"{'*'*60}\n")

    names = [f"Player_{i+1}" for i in range(num_players)]
    sb = GameSandbox(game_type=game_type, player_names=names)
    assigned = sb.auto_assign_roles()
    print("Initial Roles Assigned:")
    for a in assigned:
        print(f"  • {a}")
    print()

    for round_num in range(1, max_rounds + 1):
        winner = sb.check_win()
        if winner:
            print(f"\n🏆 Game Over! Winner: {winner} at start of Round {round_num}")
            sb.print_status()
            return winner

        # --- NIGHT PHASE ---
        sb.start_night(round_num)
        living = [p for p in sb.game.players.values() if p.is_alive]
        mafia_living = [p for p in living if p.role and p.role.alignment == "Mafia"]
        town_living = [p for p in living if p.role and p.role.alignment == "Town"]

        # Mafia kill
        mafia_killers = [p for p in mafia_living if p.can_perform_action("kill")]
        if mafia_killers and town_living:
            target = random.choice(town_living)
            killer = random.choice(mafia_killers)
            await sb.record_action(killer.display_name, "kill", target.display_name)

        # Doctor heal
        docs = [p for p in town_living if p.can_perform_action("heal")]
        for d in docs:
            eligible = [p for p in living if p.id != d.last_action_target_id]
            if eligible:
                target = random.choice(eligible)
                await sb.record_action(d.display_name, "heal", target.display_name)

        # Cop investigate
        cops = [p for p in town_living if p.can_perform_action("investigate")]
        for c in cops:
            eligible = [p for p in living if p.id != c.id]
            if eligible:
                target = random.choice(eligible)
                await sb.record_action(c.display_name, "investigate", target.display_name)

        # Roleblocker
        blockers = [p for p in living if p.can_perform_action("block")]
        for b in blockers:
            eligible = [p for p in living if p.id != b.id and p.id != b.last_action_target_id]
            if eligible:
                target = random.choice(eligible)
                await sb.record_action(b.display_name, "block", target.display_name)

        night_res = await sb.resolve_night()
        print(f"[Night {round_num}] Deaths: {[p.display_name for p in night_res['deaths']] or 'None'}")

        winner = night_res.get("winner") or sb.check_win()
        if winner:
            print(f"\n🏆 Game Over! Winner: {winner} after Night {round_num}")
            sb.print_status()
            return winner

        # --- DAY PHASE ---
        sb.start_day(round_num)
        living = [p for p in sb.game.players.values() if p.is_alive]
        if len(living) <= 1:
            winner = sb.check_win()
            print(f"\n🏆 Game Over! Winner: {winner}")
            sb.print_status()
            return winner

        # Simulate votes (majority on a random living player)
        target = random.choice(living)
        for voter in living:
            # 80% chance each player votes for the chosen target
            if random.random() < 0.8:
                await sb.cast_vote(voter.display_name, target.display_name)
            else:
                other = random.choice([p for p in living if p.id != voter.id] or [target])
                await sb.cast_vote(voter.display_name, other.display_name)

        day_res = await sb.resolve_day()
        print(f"[Day {round_num}] Lynched: {[p.display_name for p in day_res['deaths']] or 'None'}")

        winner = day_res.get("winner") or sb.check_win()
        if winner:
            print(f"\n🏆 Game Over! Winner: {winner} after Day {round_num}")
            sb.print_status()
            return winner

    print(f"\nSimulation concluded after {max_rounds} rounds.")
    sb.print_status()
    return sb.check_win()


# ==============================================================================
# Interactive CLI REPL
# ==============================================================================

async def run_interactive_cli() -> None:
    """Runs an interactive command prompt for testing game logic step-by-step."""
    print("=" * 65)
    print("  IC MAFIA BOT — GAME LOGIC TESTBED & SANDBOX")
    print("  Type 'help' for a list of commands, or 'exit' to quit.")
    print("=" * 65)

    sb = GameSandbox(game_type="classic")

    while True:
        try:
            curr_phase = sb.game.game_settings.get("current_phase", "setup")
            curr_num = sb.game.game_settings.get("phase_number", 0)
            prompt = f"\n[Sandbox:{curr_phase.upper()}_{curr_num}]> "
            user_input = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting sandbox.")
            break

        if not user_input:
            continue

        parts = user_input.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ["exit", "quit", "q"]:
            print("Goodbye!")
            break

        elif cmd == "help":
            print("""
Available Sandbox Commands:
  new [classic|battle_royale] [players...] - Create a new game with players
  add <name>                               - Add a player
  npc [name]                               - Add an NPC player
  setrole <player> <role_name>             - Assign a role to a player
  autoassign                               - Dynamically generate & assign roles
  roles                                    - List all supported role names
  players                                  - List players, roles, and status
  startday [number]                        - Switch to Day phase
  vote <voter> <target>                    - Cast a lynch vote
  votes                                    - Display current vote tally
  endday                                   - Tally votes, execute lynch, advance
  startnight [number]                      - Switch to Night phase
  action <actor> <type> <target>           - Record night action (kill/heal/block/investigate)
  actions                                  - View currently queued night actions
  endnight                                 - Resolve night actions in priority order
  checkwin                                 - Check if any team has won
  status                                   - Print full game state overview
  messages [voting|stories]                - View mock messages in a channel
  scenario <name>                          - Run a predefined scenario
  scenarios                                - List available preset scenarios
  simulate [count]                         - Run a full automated game
  reset                                    - Reset current game
            """)

        elif cmd == "new":
            mode = "classic"
            players = []
            if args:
                if args[0] in ["classic", "battle_royale"]:
                    mode = args[0]
                    players = args[1:]
                else:
                    players = args
            sb.initialize(game_type=mode, player_names=players if players else None)
            print(f"Created new {mode} game with {len(sb.game.players)} players.")

        elif cmd == "add":
            if not args:
                print("Usage: add <player_name>")
            else:
                p = sb.add_player(args[0])
                print(f"Added player: {p.display_name} (ID: {p.id})")

        elif cmd == "npc":
            name = args[0] if args else None
            p = sb.add_npc(name)
            print(f"Added NPC: {p.display_name} (ID: {p.id})")

        elif cmd == "setrole":
            if len(args) < 2:
                print("Usage: setrole <player_name> <role_name...>")
            else:
                pname = args[0]
                rname = " ".join(args[1:])
                if sb.set_player_role(pname, rname):
                    print(f"Assigned '{rname}' to {pname}.")
                else:
                    print(f"Error: Could not assign '{rname}' to {pname}. Check player and role names.")

        elif cmd == "autoassign":
            assigned = sb.auto_assign_roles()
            print(f"Auto-assigned roles to {len(assigned)} players:")
            for a in assigned:
                print(f"  • {a}")

        elif cmd == "roles":
            print("Supported Roles in role_definition.json:")
            for rname, rdata in ALL_ROLES_DATA.items():
                print(f"  • {rname:<20} | Base: {rdata.get('base', 'N/A'):<18} | Abilities: {list((rdata.get('abilities') or {}).keys())}")

        elif cmd == "players":
            sb.print_status()

        elif cmd == "startday":
            num = int(args[0]) if args and args[0].isdigit() else None
            sb.start_day(num)
            print(f"Day {sb.game.game_settings.get('phase_number')} has begun.")

        elif cmd == "vote":
            if len(args) < 2:
                print("Usage: vote <voter_name> <target_name>")
            else:
                res = await sb.cast_vote(args[0], args[1])
                print(f"Vote result: {res}")

        elif cmd == "votes":
            vt = sb.get_vote_tally()
            print("\n--- Current Vote Tally ---")
            if not vt["tally"]:
                print("  No votes have been cast yet.")
            else:
                for target, data in vt["tally"].items():
                    print(f"  • {target} ({data['count']}): {', '.join(data['voters'])}")
            if vt["not_voted"]:
                print(f"  Yet to vote ({len(vt['not_voted'])}): {', '.join(vt['not_voted'])}")
            print("--------------------------")

        elif cmd == "endday":
            res = await sb.resolve_day()
            print(f"\nDay ended!")
            if res["deaths"]:
                for d in res["deaths"]:
                    print(f"  • {d.display_name} was eliminated! ({d.death_info.get('how')})")
            else:
                print("  • No one was lynched.")
            if res["winner"]:
                print(f"\n🏆 Winner: {res['winner']}!")

        elif cmd == "startnight":
            num = int(args[0]) if args and args[0].isdigit() else None
            sb.start_night(num)
            print(f"Night {sb.game.game_settings.get('phase_number')} has begun.")

        elif cmd == "action":
            if len(args) < 3:
                print("Usage: action <actor_name> <kill|heal|block|investigate> <target_name>")
            else:
                res = await sb.record_action(args[0], args[1].lower(), args[2])
                print(f"Action result: {res}")

        elif cmd == "actions":
            queued = sb.get_queued_actions()
            print("\n--- Queued Night Actions ---")
            if not queued:
                print("  No actions currently queued.")
            else:
                for q in queued:
                    print(f"  • {q['actor']} -> {q['action'].upper()} on {q['target']} (Priority: {q['priority']})")
            print("----------------------------")

        elif cmd == "endnight":
            res = await sb.resolve_night()
            print(f"\nNight resolved!")
            if res["deaths"]:
                for d in res["deaths"]:
                    print(f"  • {d.display_name} died during the night! ({d.death_info.get('how')})")
            else:
                print("  • No one died during the night.")
            if res["blocked"]:
                print(f"  • Blocked players: {len(res['blocked'])}")
            if res["winner"]:
                print(f"\n🏆 Winner: {res['winner']}!")

        elif cmd == "checkwin":
            winner = sb.check_win()
            print(f"Win condition check: {winner or 'No winner yet. Game is ongoing.'}")

        elif cmd == "status":
            sb.print_status()

        elif cmd == "messages":
            chan_name = args[0] if args else "voting-channel"
            matched = [c for c in sb.bot.channels_by_id.values() if chan_name.lower() in c.name.lower()]
            if not matched:
                print(f"Channel '{chan_name}' not found. Available: {[c.name for c in sb.bot.channels_by_id.values()]}")
            else:
                target_chan = matched[0]
                print(f"\n--- Messages in #{target_chan.name} ({len(target_chan.messages)}) ---")
                for m in target_chan.messages[-5:]:
                    print(f"[{m['timestamp'].strftime('%H:%M:%S')}] {m['content']}")
                print("-----------------------------------------")

        elif cmd == "scenarios":
            print("Available Scenarios:")
            for sc in SCENARIOS:
                print(f"  • {sc}")

        elif cmd == "scenario":
            if not args or args[0] not in SCENARIOS:
                print(f"Usage: scenario <name>. Available: {list(SCENARIOS.keys())}")
            else:
                await SCENARIOS[args[0]]()

        elif cmd == "simulate":
            pcount = int(args[0]) if args and args[0].isdigit() else 6
            await run_full_simulation(num_players=pcount)

        elif cmd == "reset":
            sb.initialize(game_type="classic")
            print("Sandbox game reset to initial state.")

        else:
            print(f"Unknown command: '{cmd}'. Type 'help' for available commands.")


# ==============================================================================
# Main CLI Entry Point
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="IC Mafia Bot — Game Logic Testbed & Sandbox")
    parser.add_argument("--scenario", type=str, help="Run a specific preset scenario and exit", choices=list(SCENARIOS.keys()))
    parser.add_argument("--list-scenarios", action="store_true", help="List all available preset scenarios")
    parser.add_argument("--simulate", action="store_true", help="Run a full automated game simulation")
    parser.add_argument("--players", type=int, default=6, help="Number of players for simulation (default: 6)")
    parser.add_argument("--game-type", type=str, default="classic", choices=["classic", "battle_royale"], help="Game type")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")

    parsed = parser.parse_args()

    if parsed.verbose:
        logger.setLevel(logging.DEBUG)

    if parsed.list_scenarios:
        print("\nAvailable Preset Scenarios:")
        for sc, fn in SCENARIOS.items():
            doc = fn.__doc__ or "No description"
            print(f"  • {sc:<25} - {doc.strip()}")
        return

    if parsed.scenario:
        scenario_fn = SCENARIOS[parsed.scenario]
        success = asyncio.run(scenario_fn())
        sys.exit(0 if success else 1)

    if parsed.simulate:
        asyncio.run(run_full_simulation(num_players=parsed.players, game_type=parsed.game_type))
        return

    # Default: Interactive REPL
    asyncio.run(run_interactive_cli())


if __name__ == "__main__":
    main()
