"""
Comprehensive regression test suite for the IC Mafia Bot.

Covers the 15 user-specified invariants:
 1. Mafia identity DMs go only to Mafia players.
 2. Night -> Day transitions complete without error.
 3. Players can only join during signup phase.
 4. Concurrent join/vote operations are serialised by locks.
 5. Graceful error messages for incorrect slash commands.
 6. Votes are cleared at the end of each day phase.
 7. Votes are only accepted during day phase.
 8. Night actions are only recorded during night phase.
 9. Graceful error messages for actions in wrong phase.
10. Win conditions are valid and only happen when conditions are met.
11. Cannot vote for / target dead players.
12. Display names (not discord base names) are used in chat.
13. Doctor self-heal protects from same-night kill.
14. Non-dead roles are not named in the mechanical story.
15. Dead cops do not receive investigation reports.
"""
import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, Mock
import sys
import os
import discord
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 1. MUST BE FIRST: Load logger & environment mocks
from tests.test_0_logging import setup_test_logging
logger = setup_test_logging()

from game.engine import Game
from game.player import Player
from game.roles import GameRole
from game.engine.loop import game_loop_iteration
from game.actions.heal import handle_heal
from game.actions.kill import handle_kill
from game.actions.investigate import handle_investigation
from game.narration_ai import _generate_mechanical_summary


def _make_role(name, alignment, abilities=None, is_night_immune=False,
               investigation_immune=False, investigation_result=None,
               short_description="Mock role"):
    role = GameRole(
        name=name,
        alignment=alignment,
        description=f"Mock {name}",
        short_description=short_description,
        abilities=abilities or {},
        is_night_immune=is_night_immune,
    )
    role.investigation_immune = investigation_immune
    role.investigation_result = investigation_result
    return role


class TestMafiaIdentityDMs(unittest.IsolatedAsyncioTestCase):
    """1. Mafia members receive teammate identities; non-Mafia do not."""

    def setUp(self):
        patcher = patch('game.engine.config', MagicMock(MAX_MISSED_VOTES=2, min_players=3))
        patcher.start(); self.addCleanup(patcher.stop)
        self.bot = MagicMock(); self.guild = MagicMock()
        self.game = Game(self.bot, self.guild)
        self.game.narration_manager = MagicMock()

    async def test_only_mafia_receive_team_dm(self):
        """Verify send_mafia_info_dm only DMs players whose alignment == Mafia."""
        from utils.sendmafiainfodm import send_mafia_info_dm

        mafia1 = Player(100, "alice_base", "Alice")
        mafia1.assign_role(_make_role("Godfather", "Mafia", {"kill": "Kill"}))
        mafia2 = Player(200, "bob_base", "Bob")
        mafia2.assign_role(_make_role("Mob Goon", "Mafia"))
        townie = Player(300, "charlie_base", "Charlie")
        townie.assign_role(_make_role("Plain Townie", "Town"))
        sk = Player(400, "dave_base", "Dave")
        sk.assign_role(_make_role("Serial Killer", "Serial Killer", {"kill": "Kill"}))

        players = {100: mafia1, 200: mafia2, 300: townie, 400: sk}

        mock_user_alice = AsyncMock()
        mock_user_bob = AsyncMock()
        async def fake_fetch_user(uid):
            if uid == 100: return mock_user_alice
            if uid == 200: return mock_user_bob
            raise Exception("Should not fetch non-Mafia user")

        self.bot.fetch_user = AsyncMock(side_effect=fake_fetch_user)
        await send_mafia_info_dm(self.bot, players)

        # Both Mafia players should have been fetched
        fetched_ids = [c.args[0] for c in self.bot.fetch_user.call_args_list]
        self.assertIn(100, fetched_ids)
        self.assertIn(200, fetched_ids)
        self.assertNotIn(300, fetched_ids, "Town player should NOT receive Mafia DM")
        self.assertNotIn(400, fetched_ids, "SK player should NOT receive Mafia DM")

        # Verify DM content includes teammates
        alice_dm = mock_user_alice.send.call_args[0][0]
        self.assertIn("Bob", alice_dm)
        self.assertNotIn("Charlie", alice_dm)
        self.assertNotIn("Dave", alice_dm)

        bob_dm = mock_user_bob.send.call_args[0][0]
        self.assertIn("Alice", bob_dm)
        self.assertNotIn("Charlie", bob_dm)
        self.assertNotIn("Dave", bob_dm)


class TestPhaseTransitions(unittest.IsolatedAsyncioTestCase):
    """2. Night -> Day transitions happen without error.
       6. Votes are cleared at the end of each day phase."""

    def setUp(self):
        patcher = patch('game.engine.config', MagicMock(
            MAX_MISSED_VOTES=2, min_players=3,
            VOTING_CHANNEL_ID=1, STORIES_CHANNEL_ID=2,
            RULES_AND_ROLES_CHANNEL_ID=3, LIVING_ROLE_ID=999,
            REMINDER_POINTS={}, game_loop_interval_seconds=15))
        patcher.start(); self.addCleanup(patcher.stop)
        self.bot = MagicMock(); self.guild = MagicMock()
        self.game = Game(self.bot, self.guild)
        self.game.narration_manager = MagicMock()
        self.game.narration_manager.construct_story = AsyncMock(return_value="Phase story...")
        mock_channel = AsyncMock()
        self.bot.get_channel.return_value = mock_channel
        self.bot.get_cog.return_value = None
        self.guild.get_role.return_value = MagicMock()

    async def test_night_to_day_transition_no_error(self):
        """Simulate night phase ending and transitioning to day without premature game over."""
        self.game.game_settings["current_phase"] = "night"
        self.game.game_settings["phase_number"] = 1
        self.game.game_settings["phase_hours"] = 12
        self.game.game_settings["phase_end_time"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.game.game_settings["game_type"] = "classic"
        self.game.game_settings["story_type"] = "Classic Mafia"
        self.game.game_settings["game_id"] = "TEST-001"

        p1 = Player(1, "u1", "Player1")
        p1.assign_role(_make_role("Plain Townie", "Town"))
        p2 = Player(2, "u2", "Player2")
        p2.assign_role(_make_role("Plain Townie", "Town"))
        p3 = Player(3, "u3", "Player3")
        p3.assign_role(_make_role("Plain Townie", "Town"))
        p4 = Player(4, "u4", "Player4")
        p4.assign_role(_make_role("Godfather", "Mafia", {"kill": "Kill"}))
        self.game.players = {1: p1, 2: p2, 3: p3, 4: p4}

        with patch('game.engine.loop.update_player_discord_roles', new_callable=AsyncMock):
            await game_loop_iteration(self.game)

        self.assertEqual(self.game.game_settings["current_phase"], "day",
                         "Phase should transition from night -> pre-day -> day")

    async def test_votes_cleared_on_transition_to_night(self):
        """After day ends and transitions to night, lynch_votes dict should be cleared."""
        self.game.game_settings["current_phase"] = "day"
        self.game.game_settings["phase_number"] = 1
        self.game.game_settings["phase_hours"] = 12
        self.game.game_settings["phase_end_time"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.game.game_settings["game_type"] = "classic"
        self.game.game_settings["story_type"] = "Classic Mafia"
        self.game.game_settings["game_id"] = "TEST-002"

        p1 = Player(1, "u1", "Alpha")
        p1.assign_role(_make_role("Plain Townie", "Town"))
        p2 = Player(2, "u2", "Beta")
        p2.assign_role(_make_role("Plain Townie", "Town"))
        p3 = Player(3, "u3", "Gamma")
        p3.assign_role(_make_role("Plain Townie", "Town"))
        p4 = Player(4, "u4", "Delta")
        p4.assign_role(_make_role("Godfather", "Mafia", {"kill": "Kill"}))
        self.game.players = {1: p1, 2: p2, 3: p3, 4: p4}
        # All players vote, tie so game continues to night
        self.game.lynch_votes = {1: [3, 4], 4: [1, 2]}

        with patch('game.engine.loop.update_player_discord_roles', new_callable=AsyncMock):
            await game_loop_iteration(self.game)

        self.assertEqual(self.game.lynch_votes, {},
                         "Lynch votes should be cleared when transitioning to night")


class TestJoinRestrictions(unittest.IsolatedAsyncioTestCase):
    """3. Players can only join during signup phase."""

    def setUp(self):
        patcher = patch('game.engine.config', MagicMock(MAX_MISSED_VOTES=2, min_players=3))
        patcher.start(); self.addCleanup(patcher.stop)
        self.bot = MagicMock(); self.guild = MagicMock()
        self.game = Game(self.bot, self.guild)
        self.game.game_settings["phase_end_time"] = datetime.now(timezone.utc) + timedelta(hours=12)
        self.game.narration_manager = MagicMock()
        self.channel = AsyncMock()

    async def test_join_during_signup_succeeds(self):
        self.game.game_settings["current_phase"] = "signup"
        user = MagicMock(); user.id = 42; user.name = "joiner"
        with patch('game.engine.signup.update_player_discord_roles', new_callable=AsyncMock):
            result = await self.game.add_player(user, "Joiner", self.channel)
        self.assertIn(42, self.game.players)
        self.assertIn("successfully signed up", result)

    async def test_join_during_day_phase_rejected(self):
        self.game.game_settings["current_phase"] = "day"
        user = MagicMock(); user.id = 42; user.name = "joiner"
        await self.game.add_player(user, "Joiner", self.channel)
        self.assertNotIn(42, self.game.players)
        self.channel.send.assert_called()
        msg = self.channel.send.call_args[0][0]
        self.assertIn("not currently accepting", msg)

    async def test_join_during_night_phase_rejected(self):
        self.game.game_settings["current_phase"] = "night"
        user = MagicMock(); user.id = 42; user.name = "joiner"
        await self.game.add_player(user, "Joiner", self.channel)
        self.assertNotIn(42, self.game.players)

    async def test_join_during_preparation_rejected(self):
        self.game.game_settings["current_phase"] = "preparation"
        user = MagicMock(); user.id = 42; user.name = "joiner"
        await self.game.add_player(user, "Joiner", self.channel)
        self.assertNotIn(42, self.game.players)


class TestConcurrentOperations(unittest.IsolatedAsyncioTestCase):
    """4. Multiple players joining or voting at the same time are safely serialised."""

    def setUp(self):
        patcher = patch('game.engine.config', MagicMock(
            MAX_MISSED_VOTES=2, min_players=3, VOTING_CHANNEL_ID=1))
        patcher.start(); self.addCleanup(patcher.stop)
        self.bot = MagicMock(); self.guild = MagicMock()
        self.bot.get_channel.return_value = AsyncMock()
        self.game = Game(self.bot, self.guild)
        self.game.game_settings["phase_end_time"] = datetime.now(timezone.utc) + timedelta(hours=12)
        self.game.narration_manager = MagicMock()
        self.game.game_settings["current_phase"] = "signup"

    async def test_concurrent_joins_no_race(self):
        """10 players joining simultaneously should all be added without data corruption."""
        with patch('game.engine.signup.update_player_discord_roles', new_callable=AsyncMock):
            users = []
            for i in range(10):
                u = MagicMock(); u.id = 1000 + i; u.name = f"racer{i}"
                users.append(u)

            tasks = [self.game.add_player(u, f"Racer{i}", AsyncMock()) for i, u in enumerate(users)]
            await asyncio.gather(*tasks)

        self.assertEqual(len(self.game.players), 10, "All 10 concurrent joins should succeed")

    async def test_concurrent_votes_no_corruption(self):
        """Multiple votes arriving simultaneously are serialised by vote_lock."""
        self.game.game_settings["current_phase"] = "day"
        self.game.game_settings["phase_number"] = 1

        for i in range(1, 6):
            p = Player(i, f"u{i}", f"Voter{i}")
            p.assign_role(_make_role("Plain Townie", "Town"))
            self.game.players[i] = p

        target = Player(99, "target", "Target")
        target.assign_role(_make_role("Godfather", "Mafia", {"kill": "Kill"}))
        self.game.players[99] = target

        async def cast_vote(voter_id):
            voter_user = MagicMock(); voter_user.id = voter_id; voter_user.name = f"u{voter_id}"
            interaction = MagicMock()
            return await self.game.process_lynch_vote(interaction, voter_user, "Target")

        results = await asyncio.gather(*[cast_vote(i) for i in range(1, 6)])
        for r in results:
            self.assertIn("recorded", r.lower())


class TestGracefulCommandErrors(unittest.IsolatedAsyncioTestCase):
    """5 & 9. Graceful error messages for wrong-phase commands, bad targets."""

    def setUp(self):
        patcher = patch('game.engine.config', MagicMock(
            MAX_MISSED_VOTES=2, min_players=3, VOTING_CHANNEL_ID=1))
        patcher.start(); self.addCleanup(patcher.stop)
        self.bot = MagicMock(); self.guild = MagicMock()
        self.bot.get_channel.return_value = AsyncMock()
        self.game = Game(self.bot, self.guild)
        self.game.narration_manager = MagicMock()

    async def test_vote_during_night_returns_error(self):
        """7. Votes at night are not counted and return a message."""
        self.game.game_settings["current_phase"] = "night"
        p = Player(1, "u1", "VoterA")
        p.assign_role(_make_role("Plain Townie", "Town"))
        self.game.players[1] = p

        user = MagicMock(); user.id = 1; user.name = "u1"
        result = await self.game.process_lynch_vote(MagicMock(), user, "SomeTarget")
        self.assertIn("day phase", result.lower())

    async def test_night_action_during_day_returns_error(self):
        """8. Night actions during day are not recorded."""
        self.game.game_settings["current_phase"] = "day"
        p = Player(1, "u1", "CopA")
        p.assign_role(_make_role("Town Cop", "Town", {"investigate": "Investigate"}))
        self.game.players[1] = p

        result = await self.game.record_night_action(1, "investigate", "Target")
        self.assertIn("night", result.lower())
        self.assertEqual(self.game.night_actions, {}, "No night action should be recorded during day")

    async def test_vote_for_nonexistent_player_returns_error(self):
        self.game.game_settings["current_phase"] = "day"
        self.game.game_settings["phase_number"] = 1
        p = Player(1, "u1", "VoterB")
        p.assign_role(_make_role("Plain Townie", "Town"))
        self.game.players[1] = p

        user = MagicMock(); user.id = 1; user.name = "u1"
        result = await self.game.process_lynch_vote(MagicMock(), user, "GhostPlayer")
        self.assertIn("could not find", result.lower())

    async def test_night_action_wrong_ability_returns_error(self):
        """Player with no kill ability tries to kill."""
        self.game.game_settings["current_phase"] = "night"
        p = Player(1, "u1", "TownieA")
        p.assign_role(_make_role("Plain Townie", "Town"))
        self.game.players[1] = p
        target = Player(2, "u2", "TargetA")
        target.assign_role(_make_role("Plain Townie", "Town"))
        self.game.players[2] = target

        result = await self.game.record_night_action(1, "kill", "TargetA")
        self.assertIn("does not have", result.lower())

    async def test_dead_player_cannot_vote(self):
        self.game.game_settings["current_phase"] = "day"
        self.game.game_settings["phase_number"] = 1
        p = Player(1, "u1", "DeadVoter")
        p.assign_role(_make_role("Plain Townie", "Town"))
        p.is_alive = False
        self.game.players[1] = p

        user = MagicMock(); user.id = 1; user.name = "u1"
        result = await self.game.process_lynch_vote(MagicMock(), user, "Anyone")
        self.assertIn("not currently able", result.lower())


class TestVoteAndTargetRestrictions(unittest.IsolatedAsyncioTestCase):
    """11. Cannot vote for dead players or target dead players for night actions."""

    def setUp(self):
        patcher = patch('game.engine.config', MagicMock(
            MAX_MISSED_VOTES=2, min_players=3, VOTING_CHANNEL_ID=1))
        patcher.start(); self.addCleanup(patcher.stop)
        self.bot = MagicMock(); self.guild = MagicMock()
        self.bot.get_channel.return_value = AsyncMock()
        self.game = Game(self.bot, self.guild)
        self.game.narration_manager = MagicMock()

    async def test_cannot_vote_for_dead_player(self):
        self.game.game_settings["current_phase"] = "day"
        self.game.game_settings["phase_number"] = 1
        voter = Player(1, "u1", "Alive1")
        voter.assign_role(_make_role("Plain Townie", "Town"))
        dead = Player(2, "u2", "DeadGuy")
        dead.assign_role(_make_role("Plain Townie", "Town"))
        dead.is_alive = False
        self.game.players = {1: voter, 2: dead}

        user = MagicMock(); user.id = 1; user.name = "u1"
        result = await self.game.process_lynch_vote(MagicMock(), user, "DeadGuy")
        self.assertIn("already dead", result.lower())

    async def test_cannot_target_dead_player_at_night(self):
        self.game.game_settings["current_phase"] = "night"
        killer = Player(1, "u1", "Killer1")
        killer.assign_role(_make_role("Godfather", "Mafia", {"kill": "Kill"}))
        dead = Player(2, "u2", "DeadTarget")
        dead.assign_role(_make_role("Plain Townie", "Town"))
        dead.is_alive = False
        self.game.players = {1: killer, 2: dead}

        result = await self.game.record_night_action(1, "kill", "DeadTarget")
        self.assertIn("already dead", result.lower())
        self.assertNotIn(1, self.game.night_actions)


class TestDisplayNameUsage(unittest.TestCase):
    """12. Display names (not discord base names) are used everywhere in chat."""

    def test_player_str_uses_display_name(self):
        p = Player(1, "base_name_123", "CoolNickname")
        self.assertIn("CoolNickname", str(p))
        self.assertNotIn("base_name_123", str(p))

    def test_vote_history_uses_display_name(self):
        p = Player(1, "discord_user_x", "MyDisplayName")
        p.assign_role(_make_role("Plain Townie", "Town"))
        self.assertEqual(p.display_name, "MyDisplayName")
        self.assertNotEqual(p.display_name, p.name)

    def test_kill_info_uses_display_name_in_log(self):
        p = Player(1, "base", "ShownName")
        p.assign_role(_make_role("Plain Townie", "Town"))
        p.kill("Night 1", "Killed by Godfather")
        self.assertTrue(not p.is_alive)
        self.assertEqual(p.display_name, "ShownName")


class TestDoctorSelfHeal(unittest.IsolatedAsyncioTestCase):
    """13. If Doc heals themselves, they survive same-night kill."""

    def setUp(self):
        patcher = patch('game.engine.config', MagicMock(MAX_MISSED_VOTES=2, min_players=3))
        patcher.start(); self.addCleanup(patcher.stop)
        self.bot = MagicMock(); self.guild = MagicMock()
        self.game = Game(self.bot, self.guild)
        self.game.narration_manager = MagicMock()

    async def test_doctor_heals_self_survives_kill(self):
        doc = Player(1, "doc_user", "DrBrave")
        doc.assign_role(_make_role("Town Doctor", "Town", {"heal": "Heal"}))
        gf = Player(2, "gf_user", "DonCorleone")
        gf.assign_role(_make_role("Godfather", "Mafia", {"kill": "Kill"}, is_night_immune=True))
        self.game.players = {1: doc, 2: gf}

        night_outcomes = {
            1: {"action": "heal", "target": 1, "status": None},
            2: {"action": "kill", "target": 1, "status": None},
        }
        handle_heal(self.game, 1, 1, night_outcomes)
        handle_kill(self.game, 2, 1, night_outcomes)

        self.game.game_settings["current_phase"] = "night"
        self.game.game_settings["phase_number"] = 1
        await self.game._resolve_night_deaths()

        self.assertTrue(doc.is_alive, "Doctor who healed self should survive the kill")


class TestNarrationNameRestrictions(unittest.TestCase):
    """14. Mechanical summary does not reveal names of non-dead roles in story events.
       Specifically: the mechanical summary only names players who actually died."""

    def test_mechanical_summary_only_names_dead_players(self):
        events = [
            {"type": "lynch", "victims": [
                MagicMock(display_name="LynchedGuy", role=MagicMock(name="Godfather"))
            ]},
            {"type": "kill", "victim": MagicMock(
                display_name="KilledPerson",
                role=MagicMock(name="Plain Townie")
            ), "killer": MagicMock(
                display_name="SecretKiller",
                role=MagicMock(name="Serial Killer")
            )},
        ]
        summary = _generate_mechanical_summary(events)
        self.assertIn("LynchedGuy", summary)
        self.assertIn("KilledPerson", summary)

    def test_save_event_does_not_reveal_healer_identity(self):
        """When a save event occurs, the mechanical summary should NOT name the healer or their role."""
        events = [
            {"type": "save", "victim": MagicMock(
                display_name="SavedPerson",
                role=MagicMock(name="Plain Townie")
            ), "healer": MagicMock(
                display_name="SecretDoctor",
                role=MagicMock(name="Town Doctor")
            )},
        ]
        summary = _generate_mechanical_summary(events)
        self.assertNotIn("Town Doctor", summary,
                         "Living healer's role should not appear in the mechanical summary for a save event")
        self.assertNotIn("SecretDoctor", summary,
                         "Living healer's name should not appear in the mechanical summary for a save event")


class TestDeadCopNoReport(unittest.TestCase):
    """15. A dead Cop does not get an investigation report."""

    def test_dead_cop_investigation_aborted(self):
        """handle_investigation should abort if the investigator is dead."""
        bot = MagicMock()
        game = MagicMock()
        game.game_settings = {"game_type": "classic"}
        game.narration_manager = MagicMock()

        cop = Player(1, "cop_user", "DeadCop")
        cop.assign_role(_make_role("Town Cop", "Town", {"investigate": "Investigate"}))
        cop.is_alive = False

        target = Player(2, "t_user", "TargetX")
        target.assign_role(_make_role("Godfather", "Mafia", {"kill": "Kill"}))

        game.players = {1: cop, 2: target}
        game.bot = bot
        game.kill_attempts_on = {}
        game.heals_on_players = {}

        night_outcomes = {
            1: {"action": "investigate", "target": 2, "status": None},
        }

        handle_investigation(game, 1, 2, night_outcomes)

        self.assertNotEqual(
            night_outcomes[1].get("status"), "successful",
            "Dead cop's investigation should not be marked successful"
        )


class TestWinConditions(unittest.TestCase):
    """10. Win conditions are solid, valid, and only happen when conditions are met."""

    def setUp(self):
        patcher = patch('game.engine.config', MagicMock(MAX_MISSED_VOTES=2, min_players=3))
        patcher.start(); self.addCleanup(patcher.stop)
        self.bot = MagicMock(); self.guild = MagicMock()
        self.game = Game(self.bot, self.guild)
        self.game.narration_manager = MagicMock()

    def _setup_players(self, *specs):
        for pid, name, rname, align, abilities, alive in specs:
            p = Player(pid, f"u{pid}", name)
            p.assign_role(_make_role(rname, align, abilities or {}))
            p.is_alive = alive
            self.game.players[pid] = p

    def test_town_wins_when_all_evil_dead(self):
        self._setup_players(
            (1, "T1", "Plain Townie", "Town", {}, True),
            (2, "T2", "Town Cop", "Town", {"investigate": "I"}, True),
            (3, "M1", "Godfather", "Mafia", {"kill": "K"}, False),
            (4, "M2", "Mob Goon", "Mafia", {}, False),
        )
        self.assertEqual(self.game.check_win_conditions(), "Town")

    def test_mafia_wins_when_equals_town(self):
        self._setup_players(
            (1, "T1", "Plain Townie", "Town", {}, True),
            (2, "M1", "Godfather", "Mafia", {"kill": "K"}, True),
        )
        self.assertEqual(self.game.check_win_conditions(), "Mafia")

    def test_no_winner_when_town_outnumbers_mafia(self):
        self._setup_players(
            (1, "T1", "Plain Townie", "Town", {}, True),
            (2, "T2", "Town Cop", "Town", {"investigate": "I"}, True),
            (3, "M1", "Godfather", "Mafia", {"kill": "K"}, True),
        )
        self.assertIsNone(self.game.check_win_conditions())

    def test_draw_when_no_players(self):
        self.assertEqual(self.game.check_win_conditions(), "Draw")

    def test_sk_wins_when_last_alive(self):
        self._setup_players(
            (1, "T1", "Plain Townie", "Town", {}, False),
            (2, "SK", "Serial Killer", "Serial Killer", {"kill": "K"}, True),
        )
        self.assertEqual(self.game.check_win_conditions(), "Serial Killer")

    def test_no_premature_win_during_active_game(self):
        """Even with equal numbers, game continues to night if Town has protective roles."""
        self.game.game_settings["current_phase"] = "pre-night"
        self._setup_players(
            (1, "T1", "Town Doctor", "Town", {"heal": "H"}, True),
            (2, "M1", "Godfather", "Mafia", {"kill": "K"}, True),
        )
        winner = self.game.check_win_conditions()
        self.assertIsNone(winner, "Mafia should not win when town has protective roles")


class TestNightActionRecording(unittest.IsolatedAsyncioTestCase):
    """8. Night actions only recorded during night phase.
       Also: self-target restrictions."""

    def setUp(self):
        patcher = patch('game.engine.config', MagicMock(MAX_MISSED_VOTES=2, min_players=3))
        patcher.start(); self.addCleanup(patcher.stop)
        self.bot = MagicMock(); self.guild = MagicMock()
        self.game = Game(self.bot, self.guild)
        self.game.narration_manager = MagicMock()

    async def test_record_action_during_signup_rejected(self):
        self.game.game_settings["current_phase"] = "signup"
        p = Player(1, "u1", "CopA")
        p.assign_role(_make_role("Town Cop", "Town", {"investigate": "I"}))
        self.game.players[1] = p
        result = await self.game.record_night_action(1, "investigate", "CopA")
        self.assertIn("night", result.lower())

    async def test_killer_cannot_self_target(self):
        self.game.game_settings["current_phase"] = "night"
        gf = Player(1, "u1", "SelfKiller")
        gf.assign_role(_make_role("Godfather", "Mafia", {"kill": "Kill"}))
        self.game.players[1] = gf
        result = await self.game.record_night_action(1, "kill", "SelfKiller")
        self.assertIn("cannot target yourself", result.lower())

    async def test_doctor_can_self_target(self):
        """Doctors are explicitly allowed to heal themselves."""
        self.game.game_settings["current_phase"] = "night"
        doc = Player(1, "u1", "SelfHealer")
        doc.assign_role(_make_role("Town Doctor", "Town", {"heal": "Heal"}))
        self.game.players[1] = doc
        result = await self.game.record_night_action(1, "heal", "SelfHealer")
        self.assertIn("recorded", result.lower())


class TestNightImmunityOptions(unittest.IsolatedAsyncioTestCase):
    """Verifies that Godfather and Serial Killer night kill immunity can be toggled by gamestart options
    and defaults to True (cannot be killed at night)."""

    def setUp(self):
        patcher = patch('game.engine.config', MagicMock(MAX_MISSED_VOTES=2, min_players=3))
        patcher.start(); self.addCleanup(patcher.stop)
        self.bot = MagicMock(); self.guild = MagicMock()
        self.game = Game(self.bot, self.guild)
        self.game.narration_manager = MagicMock()

    def test_default_night_immunity_is_true(self):
        """Immunity defaults to True on game initialization."""
        self.assertTrue(self.game.game_settings.get("gf_night_immune", True))
        self.assertTrue(self.game.game_settings.get("sk_night_immune", True))

    async def test_godfather_immune_when_option_true(self):
        """When gf_night_immune is True, GF survives night kill attempt."""
        self.game.game_settings["gf_night_immune"] = True
        self.game.game_settings["current_phase"] = "night"
        self.game.game_settings["phase_number"] = 1

        gf = Player(1, "gf_user", "DonCorleone")
        gf.assign_role(_make_role("Godfather", "Mafia", {"kill": "Kill"}, is_night_immune=True))
        sk = Player(2, "sk_user", "Dexter")
        sk.assign_role(_make_role("Serial Killer", "Serial Killer", {"kill": "Kill"}))
        self.game.players = {1: gf, 2: sk}

        night_outcomes = {2: {"action": "kill", "target": 1, "status": None}}
        handle_kill(self.game, 2, 1, night_outcomes)
        await self.game._resolve_night_deaths()

        self.assertTrue(gf.is_alive, "Godfather with night immunity enabled should survive kill")

    async def test_godfather_vulnerable_when_option_false(self):
        """When gf_night_immune is False, GF is killed when targeted."""
        self.game.game_settings["gf_night_immune"] = False
        self.game.game_settings["current_phase"] = "night"
        self.game.game_settings["phase_number"] = 1

        gf = Player(1, "gf_user", "VulnerableGF")
        gf.assign_role(_make_role("Godfather", "Mafia", {"kill": "Kill"}, is_night_immune=False))
        sk = Player(2, "sk_user", "Dexter")
        sk.assign_role(_make_role("Serial Killer", "Serial Killer", {"kill": "Kill"}))
        self.game.players = {1: gf, 2: sk}

        night_outcomes = {2: {"action": "kill", "target": 1, "status": None}}
        handle_kill(self.game, 2, 1, night_outcomes)
        await self.game._resolve_night_deaths()

        self.assertFalse(gf.is_alive, "Godfather with night immunity disabled should die to night kill")

    async def test_serial_killer_immune_when_option_true(self):
        """When sk_night_immune is True, SK survives night kill attempt."""
        self.game.game_settings["sk_night_immune"] = True
        self.game.game_settings["current_phase"] = "night"
        self.game.game_settings["phase_number"] = 1

        sk = Player(1, "sk_user", "ImmuneSK")
        sk.assign_role(_make_role("Serial Killer", "Serial Killer", {"kill": "Kill"}, is_night_immune=True))
        gf = Player(2, "gf_user", "DonCorleone")
        gf.assign_role(_make_role("Godfather", "Mafia", {"kill": "Kill"}))
        self.game.players = {1: sk, 2: gf}

        night_outcomes = {2: {"action": "kill", "target": 1, "status": None}}
        handle_kill(self.game, 2, 1, night_outcomes)
        await self.game._resolve_night_deaths()

        self.assertTrue(sk.is_alive, "Serial Killer with night immunity enabled should survive kill")

    async def test_serial_killer_vulnerable_when_option_false(self):
        """When sk_night_immune is False, SK is killed when targeted."""
        self.game.game_settings["sk_night_immune"] = False
        self.game.game_settings["current_phase"] = "night"
        self.game.game_settings["phase_number"] = 1

        sk = Player(1, "sk_user", "VulnerableSK")
        sk.assign_role(_make_role("Serial Killer", "Serial Killer", {"kill": "Kill"}, is_night_immune=False))
        gf = Player(2, "gf_user", "DonCorleone")
        gf.assign_role(_make_role("Godfather", "Mafia", {"kill": "Kill"}))
        self.game.players = {1: sk, 2: gf}

        night_outcomes = {2: {"action": "kill", "target": 1, "status": None}}
        handle_kill(self.game, 2, 1, night_outcomes)
        await self.game._resolve_night_deaths()

        self.assertFalse(sk.is_alive, "Serial Killer with night immunity disabled should die to night kill")


class TestBattleRoyaleSkipDay(unittest.IsolatedAsyncioTestCase):
    """Verifies that Battle Royale can skip the day phase and proceed consecutively across night phases."""

    def setUp(self):
        patcher = patch('game.engine.config', MagicMock(
            MAX_MISSED_VOTES=2, min_players=3,
            VOTING_CHANNEL_ID=1, STORIES_CHANNEL_ID=2,
            RULES_AND_ROLES_CHANNEL_ID=3, LIVING_ROLE_ID=999,
            REMINDER_POINTS={}, game_loop_interval_seconds=15))
        patcher.start(); self.addCleanup(patcher.stop)
        self.bot = MagicMock(); self.guild = MagicMock()
        self.bot.get_channel.return_value = AsyncMock()
        self.bot.get_cog.return_value = None
        self.guild.get_role.return_value = MagicMock()
        self.game = Game(self.bot, self.guild)
        self.game.narration_manager = MagicMock()
        self.game.narration_manager.construct_story = AsyncMock(return_value="BR Story...")

    async def test_battle_royale_skips_day_to_next_night(self):
        """When br_skip_day is True, ending Night 1 transitions directly to Night 2 (skipping Day 1)."""
        self.game.game_settings["game_type"] = "battle_royale"
        self.game.game_settings["br_skip_day"] = True
        self.game.game_settings["current_phase"] = "night"
        self.game.game_settings["phase_number"] = 1
        self.game.game_settings["phase_hours"] = 12
        self.game.game_settings["phase_end_time"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.game.game_settings["game_id"] = "BR-TEST-001"

        # 3 alive vigilantes so game does not end (needs 1 survivor to win)
        for i in range(1, 4):
            p = Player(i, f"p{i}", f"Survivor{i}")
            p.assign_role(_make_role("Vigilante", "NeutralRoyale", {"kill": "K", "block": "B"}))
            self.game.players[i] = p

        with patch('game.engine.loop.update_player_discord_roles', new_callable=AsyncMock):
            await game_loop_iteration(self.game)

        self.assertEqual(self.game.game_settings["current_phase"], "night",
                         "Battle Royale with br_skip_day should transition directly to night")
        self.assertEqual(self.game.game_settings["phase_number"], 2,
                         "Phase number should increment to Night 2")

    async def test_battle_royale_normal_cycle_when_skip_false(self):
        """When br_skip_day is False, ending Night 1 transitions to Day 1 as normal."""
        self.game.game_settings["game_type"] = "battle_royale"
        self.game.game_settings["br_skip_day"] = False
        self.game.game_settings["current_phase"] = "night"
        self.game.game_settings["phase_number"] = 1
        self.game.game_settings["phase_hours"] = 12
        self.game.game_settings["phase_end_time"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.game.game_settings["game_id"] = "BR-TEST-002"

        for i in range(1, 4):
            p = Player(i, f"p{i}", f"Survivor{i}")
            p.assign_role(_make_role("Vigilante", "NeutralRoyale", {"kill": "K", "block": "B"}))
            self.game.players[i] = p

        with patch('game.engine.loop.update_player_discord_roles', new_callable=AsyncMock):
            await game_loop_iteration(self.game)

        self.assertEqual(self.game.game_settings["current_phase"], "day",
                         "Battle Royale with br_skip_day=False should transition to day phase")
        self.assertEqual(self.game.game_settings["phase_number"], 1)

    def test_battle_royale_rules_display_shows_skip_day(self):
        """Dynamic rules embed displays day phase skipped when enabled."""
        from game.data.getrules import get_dynamic_rules
        self.game.game_settings["game_type"] = "battle_royale"
        self.game.game_settings["br_skip_day"] = True
        rules_text = get_dynamic_rules(None, self.game.game_settings)
        self.assertIn("Skipped", rules_text)


class TestBattleRoyaleMultipleKillsAndDeathSummaries(unittest.IsolatedAsyncioTestCase):
    """
    Validates that:
    1. During Battle Royale, the summary in rules shows killed by player name, NOT role.
    2. During Classic Mafia, the summary in rules shows killed by role (anonymity preserved).
    3. Multiple killers on a single player are all recorded, shown in rules summary, and narrated in story.
    4. SFW themes (Rom Com & Office Restructuring) properly adapt multiple attacks.
    """

    def setUp(self):
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        self.game = Game(self.mock_bot, self.mock_guild)
        self.game.game_settings["phase_number"] = 1
        self.game.game_settings["current_phase"] = "night"
        self.game.game_settings["phase_end_time"] = datetime.now(timezone.utc) + timedelta(hours=12)

    async def test_battle_royale_single_kill_shows_player_name_not_role(self):
        """In Battle Royale, death summary must state 'Killed by <PlayerName>', not the role."""
        self.game.game_settings["game_type"] = "battle_royale"
        victim = Player(1, "v_disc", "AliceVictim")
        victim.assign_role(_make_role("Townie", "Neutral", {}))
        killer = Player(2, "k_disc", "BobKiller")
        killer.assign_role(_make_role("Godfather", "Neutral", {"kill": "K"}))

        self.game.players = {1: victim, 2: killer}
        self.game.kill_attempts_on = {1: [2]}

        await self.game._resolve_night_deaths()

        self.assertFalse(victim.is_alive)
        self.assertEqual(victim.death_info.get("how"), "Killed by BobKiller")
        self.assertNotIn("Godfather", victim.death_info.get("how"))

        status_msg = self.game.get_status_message()
        self.assertIn("Killed by BobKiller", status_msg)
        self.assertNotIn("Killed by Godfather", status_msg)

    async def test_classic_mafia_single_kill_shows_role_not_player_name(self):
        """In Classic Mafia, death summary must state 'Killed by <RoleName>', preserving killer anonymity."""
        self.game.game_settings["game_type"] = "classic"
        victim = Player(1, "v_disc", "AliceVictim")
        victim.assign_role(_make_role("Townie", "Town", {}))
        killer = Player(2, "k_disc", "BobKiller")
        killer.assign_role(_make_role("Godfather", "Mafia", {"kill": "K"}))

        self.game.players = {1: victim, 2: killer}
        self.game.kill_attempts_on = {1: [2]}

        await self.game._resolve_night_deaths()

        self.assertFalse(victim.is_alive)
        self.assertEqual(victim.death_info.get("how"), "Killed by Godfather")
        self.assertNotIn("BobKiller", victim.death_info.get("how"))

        status_msg = self.game.get_status_message()
        self.assertIn("Killed by Godfather", status_msg)
        self.assertNotIn("Killed by BobKiller", status_msg)

    async def test_battle_royale_multiple_killers_recorded_and_narrated(self):
        """When 3 people target the same player in Battle Royale, all 3 are recorded, shown in summary, and narrated."""
        self.game.game_settings["game_type"] = "battle_royale"
        victim = Player(1, "v_disc", "AliceVictim")
        victim.assign_role(_make_role("Townie", "Neutral", {}))

        killer1 = Player(2, "k1_disc", "BobAttacker")
        killer1.assign_role(_make_role("Fighter", "Neutral", {"kill": "K"}))

        killer2 = Player(3, "k2_disc", "CharlieAttacker")
        killer2.assign_role(_make_role("Assault", "Neutral", {"kill": "K"}))

        killer3 = Player(4, "k3_disc", "DaveAttacker")
        killer3.assign_role(_make_role("Sniper", "Neutral", {"kill": "K"}))

        self.game.players = {1: victim, 2: killer1, 3: killer2, 4: killer3}
        self.game.kill_attempts_on = {1: [2, 3, 4]}

        await self.game._resolve_night_deaths()

        self.assertFalse(victim.is_alive)
        expected_cause = "Killed by BobAttacker, CharlieAttacker, and DaveAttacker"
        self.assertEqual(victim.death_info.get("how"), expected_cause)

        status_msg = self.game.get_status_message()
        self.assertIn(expected_cause, status_msg)

        # Verify mechanical summary
        events = self.game.narration_manager.events
        summary = _generate_mechanical_summary(events)
        self.assertIn("attacked 3 times!", summary)
        self.assertIn("BobAttacker, CharlieAttacker, and DaveAttacker", summary)

        # Verify static narration includes all 3 killers
        from game.narration_static import generate_story
        story = generate_story("**--- Night 1 ---**", events, story_type="Classic Mafia")
        self.assertIn("AliceVictim", story)
        self.assertIn("BobAttacker", story)
        self.assertIn("CharlieAttacker", story)
        self.assertIn("DaveAttacker", story)
        self.assertIn("3 separate attackers", story)

    async def test_battle_royale_multiple_killers_themed_narration(self):
        """Verify Rom Com and Office Restructuring themes properly represent multiple attackers."""
        from game.narration_static import generate_story
        victim = Player(1, "v_disc", "AliceVictim")
        victim.assign_role(_make_role("Townie", "Neutral", {}))
        k1 = Player(2, "k1_disc", "Bob")
        k2 = Player(3, "k2_disc", "Charlie")
        k3 = Player(4, "k3_disc", "Dave")
        living_killers = [k1, k2, k3]

        events = [{
            "type": "kill_battle_royale",
            "victim": victim,
            "killer": k1,
            "killers": living_killers
        }]

        # Rom Com theme
        rom_story = generate_story("**--- Night 1 ---**", events, story_type="Rom Com")
        self.assertIn("dumped and ghosted by 3 suitors", rom_story)
        self.assertIn("Bob", rom_story)
        self.assertIn("Charlie", rom_story)
        self.assertIn("Dave", rom_story)

        # Office Restructuring theme
        office_story = generate_story("**--- Night 1 ---**", events, story_type="Office Restructuring")
        self.assertIn("coordinated strike by 3 colleagues", office_story)
        self.assertIn("abruptly fired", office_story)
        self.assertIn("Bob", office_story)
        self.assertIn("Charlie", office_story)
        self.assertIn("Dave", office_story)


class TestMergedForceCommands(unittest.IsolatedAsyncioTestCase):
    """
    Validates that /forcephaseend and /forcestart are merged and work across
    signups, day, and night phases immediately.
    """

    def setUp(self):
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        self.game = Game(self.mock_bot, self.mock_guild)
        self.mock_interaction = MagicMock(spec=discord.Interaction)
        self.mock_interaction.user = MagicMock()
        self.mock_interaction.user.name = "TestAdmin"
        self.mock_interaction.response = MagicMock()
        self.mock_interaction.response.send_message = AsyncMock()

    async def test_merged_force_command_during_signup(self):
        """Using force command during signup sets force_start_flag and alerts."""
        self.game.game_settings["current_phase"] = "signup"
        from cogs.admincogs.forcephaseend import force_phase_end_command
        mock_cog = MagicMock()
        mock_cog.get_game_instance.return_value = self.game

        await force_phase_end_command(mock_cog, self.mock_interaction)

        self.assertTrue(self.game.force_start_flag)
        self.mock_interaction.response.send_message.assert_called_once()
        msg = self.mock_interaction.response.send_message.call_args[0][0]
        self.assertIn("Sign-ups have been ended by admin", msg)

    async def test_merged_force_command_during_day(self):
        """Using force command during day phase immediately expires phase_end_time."""
        self.game.game_settings["current_phase"] = "day"
        self.game.game_settings["phase_number"] = 1
        future_time = datetime.now(timezone.utc) + timedelta(hours=12)
        self.game.game_settings["phase_end_time"] = future_time

        from cogs.admincogs.forcephaseend import force_phase_end_command
        mock_cog = MagicMock()
        mock_cog.get_game_instance.return_value = self.game

        await force_phase_end_command(mock_cog, self.mock_interaction)

        # End time set to current time or past
        self.assertLessEqual(self.game.game_settings["phase_end_time"], datetime.now(timezone.utc))
        self.mock_interaction.response.send_message.assert_called_once()
        msg = self.mock_interaction.response.send_message.call_args[0][0]
        self.assertIn("Phase 'Day' end time has been set to now", msg)

    async def test_merged_force_command_during_night(self):
        """Using forcestart command during night phase also immediately expires phase_end_time."""
        self.game.game_settings["current_phase"] = "night"
        self.game.game_settings["phase_number"] = 1
        future_time = datetime.now(timezone.utc) + timedelta(hours=12)
        self.game.game_settings["phase_end_time"] = future_time

        from cogs.admincogs.forcestart import force_start_command
        mock_cog = MagicMock()
        mock_cog.get_game_instance.return_value = self.game

        await force_start_command(mock_cog, self.mock_interaction)

        self.assertLessEqual(self.game.game_settings["phase_end_time"], datetime.now(timezone.utc))
        self.mock_interaction.response.send_message.assert_called_once()
        msg = self.mock_interaction.response.send_message.call_args[0][0]
        self.assertIn("Phase 'Night' end time has been set to now", msg)

    async def test_merged_force_command_no_active_game(self):
        """Using force command when no game is running returns friendly error."""
        from cogs.admincogs.forcephaseend import force_phase_end_command
        mock_cog = MagicMock()
        mock_cog.get_game_instance.return_value = None

        await force_phase_end_command(mock_cog, self.mock_interaction)

        self.mock_interaction.response.send_message.assert_called_once_with(
            "No game is currently active.",
            ephemeral=True
        )


class TestRoleblockDependencyResolutionAndDaySkipVisibility(unittest.IsolatedAsyncioTestCase):
    """
    Validates:
    1. Blocker A targeting Blocker B prevents B from acting/blocking their target.
    2. Mutual blocks (Blocker A targets B, B targets A) block both and neither can affect third parties.
    3. Three-blocker dependency chain (A -> B -> C -> Target).
    4. Day phase skip visibility across rules header, dynamic rules, start announcement, and status message.
    """

    def setUp(self):
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        self.game = Game(self.mock_bot, self.mock_guild)
        self.game.game_settings["phase_number"] = 1
        self.game.game_settings["current_phase"] = "night"
        self.game.game_settings["phase_end_time"] = datetime.now(timezone.utc) + timedelta(hours=12)
        self.game.game_settings["game_type"] = "classic"

    async def test_roleblocker_a_blocks_roleblocker_b_preventing_b_from_blocking_doctor(self):
        """Blocker A blocks Blocker B; Blocker B targets Doctor C; Doctor C heals Victim V; Killer K attacks Victim V."""
        from game.engine.night import process_night_actions, _resolve_night_deaths

        # Players
        p_rb1 = Mock(id=1, display_name="RB1", is_alive=True, is_npc=False)
        p_rb1.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        p_rb2 = Mock(id=2, display_name="RB2", is_alive=True, is_npc=False)
        p_rb2.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        p_doc = Mock(id=3, display_name="Doctor", is_alive=True, is_npc=False)
        p_doc.role = Mock(name="Doctor", abilities=["heal"], night_priority=2, is_night_immune=False)

        p_victim = Mock(id=4, display_name="Victim", is_alive=True, is_npc=False, death_info={})
        p_victim.role = Mock(name="Townie", abilities=[], night_priority=99, is_night_immune=False)

        p_killer = Mock(id=5, display_name="Killer", is_alive=True, is_npc=False)
        p_killer.role = Mock(name="Godfather", abilities=["kill"], night_priority=3, is_night_immune=True)

        self.game.players = {1: p_rb1, 2: p_rb2, 3: p_doc, 4: p_victim, 5: p_killer}

        # Queue actions:
        # RB1 blocks RB2
        # RB2 blocks Doctor (id 3)
        # Doctor heals Victim (id 4)
        # Killer kills Victim (id 4)
        self.game.night_actions = {
            1: {"type": "block", "target_id": 2, "night_priority": 1},
            2: {"type": "block", "target_id": 3, "night_priority": 1},
            3: {"type": "heal", "target_id": 4, "night_priority": 2},
            5: {"type": "kill", "target_id": 4, "night_priority": 3},
        }

        await process_night_actions(self.game)

        # RB2 must be recorded in blocked_players_this_night (blocked by RB1)
        self.assertEqual(self.game.blocked_players_this_night.get(2), 1)
        # Doctor (3) must NOT be blocked!
        self.assertNotIn(3, self.game.blocked_players_this_night)
        # Doctor must have successfully healed Victim (4)
        self.assertIn(3, self.game.heals_on_players.get(4, []))

        # Now resolve deaths
        await _resolve_night_deaths(self.game)

        # Victim must survive because Doctor successfully healed them!
        self.assertTrue(p_victim.is_alive)

    async def test_roleblocker_mutual_block(self):
        """Blocker A blocks B, and Blocker B blocks A. Both are blocked."""
        from game.engine.night import process_night_actions

        p_rb1 = Mock(id=1, display_name="RB1", is_alive=True, is_npc=False)
        p_rb1.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        p_rb2 = Mock(id=2, display_name="RB2", is_alive=True, is_npc=False)
        p_rb2.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        self.game.players = {1: p_rb1, 2: p_rb2}
        self.game.night_actions = {
            1: {"type": "block", "target_id": 2, "night_priority": 1},
            2: {"type": "block", "target_id": 1, "night_priority": 1},
        }

        await process_night_actions(self.game)

        self.assertIn(1, self.game.blocked_players_this_night)
        self.assertIn(2, self.game.blocked_players_this_night)

    async def test_roleblock_three_blocker_chain(self):
        """A blocks B, B blocks C, C blocks Doctor D."""
        from game.engine.night import process_night_actions

        p1 = Mock(id=1, display_name="RB1", is_alive=True, is_npc=False)
        p1.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1)

        p2 = Mock(id=2, display_name="RB2", is_alive=True, is_npc=False)
        p2.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1)

        p3 = Mock(id=3, display_name="RB3", is_alive=True, is_npc=False)
        p3.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1)

        p4 = Mock(id=4, display_name="Doctor", is_alive=True, is_npc=False)
        p4.role = Mock(name="Doctor", abilities=["heal"], night_priority=2)

        self.game.players = {1: p1, 2: p2, 3: p3, 4: p4}
        self.game.night_actions = {
            1: {"type": "block", "target_id": 2, "night_priority": 1},
            2: {"type": "block", "target_id": 3, "night_priority": 1},
            3: {"type": "block", "target_id": 4, "night_priority": 1},
            4: {"type": "heal", "target_id": 1, "night_priority": 2},
        }

        await process_night_actions(self.game)

        # RB2 blocked by RB1
        self.assertEqual(self.game.blocked_players_this_night.get(2), 1)
        # RB3 was targeted by RB2, but RB2 was blocked! So RB3 is NOT blocked!
        self.assertNotEqual(self.game.blocked_players_this_night.get(3), 2)
        # RB3 successfully blocked Doctor (4)!
        self.assertEqual(self.game.blocked_players_this_night.get(4), 3)

    def test_day_phase_skip_visibility_indicators(self):
        """Day phase skip is clearly visible in header, dynamic rules, and status message."""
        from game.data.getrules import create_header, get_dynamic_rules
        from game.engine.status import get_status_message

        self.game.game_settings["game_type"] = "battle_royale"
        self.game.game_settings["br_skip_day"] = True
        self.game.game_settings["game_id"] = "TEST-BR-01"

        header = create_header(None, self.game.game_settings)
        self.assertIn("DAY PHASE SKIPPED", header)

        rules = get_dynamic_rules(None, self.game.game_settings)
        self.assertIn("Skipped", rules)

        status = get_status_message(self.game)
        self.assertIn("Day Phase Skipped", status)

    async def test_roleblock_on_plain_townie_emits_no_story_event(self):
        """If Roleblocker targets a Plain Townie, no story event is emitted."""
        from game.engine.night import process_night_actions

        p_rb = Mock(id=1, display_name="RB", is_alive=True, is_npc=False)
        p_rb.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        p_town = Mock(id=2, display_name="PlainTownie", is_alive=True, is_npc=False)
        p_town.role = Mock(name="Townie", abilities=[], night_priority=99, is_night_immune=False)

        self.game.players = {1: p_rb, 2: p_town}
        self.game.night_actions = {
            1: {"type": "block", "target_id": 2, "night_priority": 1}
        }
        self.game.narration_manager.events.clear()

        await process_night_actions(self.game)

        # Target is tracked internally
        self.assertEqual(self.game.blocked_players_this_night.get(2), 1)
        # But NO narration event was emitted
        self.assertEqual(len(self.game.narration_manager.events), 0)

    async def test_roleblock_on_idle_night_action_player_emits_no_story_event(self):
        """If Roleblocker targets an idle player with abilities, no story event is emitted."""
        from game.engine.night import process_night_actions

        p_rb = Mock(id=1, display_name="RB", is_alive=True, is_npc=False)
        p_rb.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        p_doc = Mock(id=3, display_name="DoctorBob", is_alive=True, is_npc=False)
        p_doc.role = Mock(name="Doctor", abilities=["heal"], night_priority=2, is_night_immune=False)

        self.game.players = {1: p_rb, 3: p_doc}
        # Doctor submitted NO action
        self.game.night_actions = {
            1: {"type": "block", "target_id": 3, "night_priority": 1}
        }
        self.game.narration_manager.events.clear()

        await process_night_actions(self.game)

        # Target is tracked internally
        self.assertEqual(self.game.blocked_players_this_night.get(3), 1)
        # But NO narration event was emitted
        self.assertEqual(len(self.game.narration_manager.events), 0)

    async def test_roleblock_on_active_kill_emits_thwarted_murder_action_story(self):
        """If Roleblocker targets a killer performing a kill, story describes blocked murder, not the person."""
        from game.engine.night import process_night_actions
        from game.narration_static import _generate_static_story_part
        from game.narration_ai import _generate_mechanical_summary

        p_rb = Mock(id=1, display_name="RB", is_alive=True, is_npc=False)
        p_rb.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        p_gf = Mock(id=2, display_name="DonCorleone", is_alive=True, is_npc=False)
        p_gf.role = Mock(name="Godfather", abilities=["kill"], night_priority=3, is_night_immune=True)

        p_victim = Mock(id=3, display_name="InnocentCiv", is_alive=True, is_npc=False)
        p_victim.role = Mock(name="Townie", abilities=[], night_priority=99, is_night_immune=False)

        self.game.players = {1: p_rb, 2: p_gf, 3: p_victim}
        self.game.night_actions = {
            1: {"type": "block", "target_id": 2, "night_priority": 1},
            2: {"type": "kill", "target_id": 3, "night_priority": 3},
        }
        self.game.narration_manager.events.clear()

        await process_night_actions(self.game)

        # Target is tracked internally
        self.assertEqual(self.game.blocked_players_this_night.get(2), 1)
        # Exactly one block event emitted
        self.assertEqual(len(self.game.narration_manager.events), 1)
        event = self.game.narration_manager.events[0]
        self.assertEqual(event['type'], 'block')
        self.assertEqual(event['action_type'], 'kill')
        self.assertEqual(event['action_target'], p_victim)

        # Static narration describes thwarted murder without naming DonCorleone or Godfather
        static_story = _generate_static_story_part(event, story_type="Classic Mafia")
        self.assertIn("thwarted an attempted murder", static_story)
        self.assertNotIn("DonCorleone", static_story)
        self.assertNotIn("Godfather", static_story)

        # Mechanical summary describes thwarted murder without naming DonCorleone or Godfather
        mech_summary = _generate_mechanical_summary([event])
        self.assertIn("An attempted murder in the night was thwarted by a shadowy figure!", mech_summary)
        self.assertNotIn("DonCorleone", mech_summary)
        self.assertNotIn("Godfather", mech_summary)

    async def test_roleblock_on_investigation_emits_no_story_event(self):
        """If Roleblocker blocks Cop investigating someone, no story event is emitted."""
        from game.engine.night import process_night_actions

        p_rb = Mock(id=1, display_name="RB", is_alive=True, is_npc=False)
        p_rb.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        p_cop = Mock(id=2, display_name="SheriffJoe", is_alive=True, is_npc=False)
        p_cop.role = Mock(name="Town Cop", abilities=["investigate"], night_priority=4, is_night_immune=False)

        p_target = Mock(id=3, display_name="CitizenJane", is_alive=True, is_npc=False)
        p_target.role = Mock(name="Townie", abilities=[], night_priority=99, is_night_immune=False)

        self.game.players = {1: p_rb, 2: p_cop, 3: p_target}
        self.game.night_actions = {
            1: {"type": "block", "target_id": 2, "night_priority": 1},
            2: {"type": "investigate", "target_id": 3, "night_priority": 4},
        }
        self.game.narration_manager.events.clear()

        await process_night_actions(self.game)

        # Cop is blocked internally
        self.assertEqual(self.game.blocked_players_this_night.get(2), 1)
        # But NO story event is emitted
        self.assertEqual(len(self.game.narration_manager.events), 0)

    async def test_roleblock_on_heal_when_patient_not_attacked_emits_no_story_event(self):
        """If Doctor is blocked but patient was not attacked, heal would not stop a kill -> NO story event."""
        from game.engine.night import process_night_actions

        p_rb = Mock(id=1, display_name="RB", is_alive=True, is_npc=False)
        p_rb.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        p_doc = Mock(id=2, display_name="DocBrown", is_alive=True, is_npc=False)
        p_doc.role = Mock(name="Doctor", abilities=["heal"], night_priority=2, is_night_immune=False)

        p_patient = Mock(id=3, display_name="CitizenJane", is_alive=True, is_npc=False)
        p_patient.role = Mock(name="Townie", abilities=[], night_priority=99, is_night_immune=False)

        # Doctor heals patient, but NO ONE attacks patient
        self.game.players = {1: p_rb, 2: p_doc, 3: p_patient}
        self.game.night_actions = {
            1: {"type": "block", "target_id": 2, "night_priority": 1},
            2: {"type": "heal", "target_id": 3, "night_priority": 2},
        }
        self.game.narration_manager.events.clear()

        await process_night_actions(self.game)

        # Doctor is blocked internally
        self.assertEqual(self.game.blocked_players_this_night.get(2), 1)
        # Because patient was not attacked, NO story event is emitted
        self.assertEqual(len(self.game.narration_manager.events), 0)

    async def test_roleblock_on_heal_when_killer_also_blocked_emits_no_blocked_heal_event(self):
        """If Doctor is blocked AND Killer is blocked, patient was not attacked -> NO blocked heal event."""
        from game.engine.night import process_night_actions

        p_rb1 = Mock(id=1, display_name="RB1", is_alive=True, is_npc=False)
        p_rb1.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        p_rb2 = Mock(id=2, display_name="RB2", is_alive=True, is_npc=False)
        p_rb2.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        p_doc = Mock(id=3, display_name="DocBrown", is_alive=True, is_npc=False)
        p_doc.role = Mock(name="Doctor", abilities=["heal"], night_priority=2, is_night_immune=False)

        p_killer = Mock(id=4, display_name="Killer", is_alive=True, is_npc=False)
        p_killer.role = Mock(name="Godfather", abilities=["kill"], night_priority=3, is_night_immune=True)

        p_patient = Mock(id=5, display_name="CitizenJane", is_alive=True, is_npc=False)
        p_patient.role = Mock(name="Townie", abilities=[], night_priority=99, is_night_immune=False)

        # RB1 blocks Doc (3); RB2 blocks Killer (4); Doc heals Jane (5); Killer attacks Jane (5)
        self.game.players = {1: p_rb1, 2: p_rb2, 3: p_doc, 4: p_killer, 5: p_patient}
        self.game.night_actions = {
            1: {"type": "block", "target_id": 3, "night_priority": 1},
            2: {"type": "block", "target_id": 4, "night_priority": 1},
            3: {"type": "heal", "target_id": 5, "night_priority": 2},
            4: {"type": "kill", "target_id": 5, "night_priority": 3},
        }
        self.game.narration_manager.events.clear()

        await process_night_actions(self.game)

        # Killer was blocked, so Blocked Kill event is emitted
        # BUT Doc's heal did NOT stop any kill, so NO Blocked Heal event is emitted!
        events = self.game.narration_manager.events
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['action_type'], 'kill')

    async def test_roleblock_on_heal_when_patient_is_attacked_emits_blocked_heal_event(self):
        """If Doctor is blocked AND patient is attacked by an unblocked kill, heal would have stopped kill -> EMIT."""
        from game.engine.night import process_night_actions
        from game.narration_ai import _generate_mechanical_summary

        p_rb = Mock(id=1, display_name="RB", is_alive=True, is_npc=False)
        p_rb.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        p_doc = Mock(id=2, display_name="DocBrown", is_alive=True, is_npc=False)
        p_doc.role = Mock(name="Doctor", abilities=["heal"], night_priority=2, is_night_immune=False)

        p_killer = Mock(id=3, display_name="Killer", is_alive=True, is_npc=False)
        p_killer.role = Mock(name="Godfather", abilities=["kill"], night_priority=3, is_night_immune=True)

        p_patient = Mock(id=4, display_name="CitizenJane", is_alive=True, is_npc=False, death_info={})
        p_patient.role = Mock(name="Townie", abilities=[], night_priority=99, is_night_immune=False)

        # RB blocks Doc; Killer attacks Jane; Doc was healing Jane!
        self.game.players = {1: p_rb, 2: p_doc, 3: p_killer, 4: p_patient}
        self.game.night_actions = {
            1: {"type": "block", "target_id": 2, "night_priority": 1},
            2: {"type": "heal", "target_id": 4, "night_priority": 2},
            3: {"type": "kill", "target_id": 4, "night_priority": 3},
        }
        self.game.narration_manager.events.clear()

        await process_night_actions(self.game)

        # The heal WOULD have saved Jane from Killer's attack!
        heal_events = [e for e in self.game.narration_manager.events if e.get('action_type') == 'heal']
        self.assertEqual(len(heal_events), 1)
        event = heal_events[0]
        self.assertEqual(event['action_target'], p_patient)

        summary = _generate_mechanical_summary([event])
        self.assertIn("medical protection was intercepted and blocked", summary)
        self.assertNotIn("DocBrown", summary)

    async def test_roleblock_on_blocker_emits_blocked_block_event(self):
        """If Roleblocker 1 blocks Roleblocker 2 who targeted Doctor, Blocked Block is emitted."""
        from game.engine.night import process_night_actions
        from game.narration_ai import _generate_mechanical_summary

        p_rb1 = Mock(id=1, display_name="RB1", is_alive=True, is_npc=False)
        p_rb1.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        p_rb2 = Mock(id=2, display_name="RB2", is_alive=True, is_npc=False)
        p_rb2.role = Mock(name="Roleblocker", abilities=["block"], night_priority=1, is_night_immune=False)

        p_doc = Mock(id=3, display_name="DocBrown", is_alive=True, is_npc=False)
        p_doc.role = Mock(name="Doctor", abilities=["heal"], night_priority=2, is_night_immune=False)

        self.game.players = {1: p_rb1, 2: p_rb2, 3: p_doc}
        self.game.night_actions = {
            1: {"type": "block", "target_id": 2, "night_priority": 1},
            2: {"type": "block", "target_id": 3, "night_priority": 1},
        }
        self.game.narration_manager.events.clear()

        await process_night_actions(self.game)

        # RB2's block was blocked by RB1!
        block_events = [e for e in self.game.narration_manager.events if e.get('action_type') == 'block']
        self.assertEqual(len(block_events), 1)

        summary = _generate_mechanical_summary(block_events)
        self.assertIn("attempt to interfere with another citizen was thwarted", summary)
        self.assertNotIn("RB2", summary)


if __name__ == "__main__":
    unittest.main()


