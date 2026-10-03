import unittest
from unittest.mock import MagicMock
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_0_logging import setup_test_logging
logger = setup_test_logging()

import game.roles as roles_module
from game.roles import get_role_instance, GameRole
from game.engine.prepare import generate_game_roles
import game.narration_static as static_storyteller
import game.narration_ai as ai_storyteller
from game.engine.status import get_status_message

from datetime import datetime, timezone, timedelta

EXPECTED_THEMES = [
    "Classic Mafia",
    "Horror",
    "Explicit Kinky NSFW",
    "Rom Com",
    "Office Restructuring",
    "High Fantasy",
    "Cyberpunk",
    "Comedy",
    "Lovecraftian Horror"
]

CANONICAL_ROLES = [
    "Town Cop",
    "Town Doctor",
    "Plain Townie",
    "Town Role Blocker",
    "Godfather",
    "Mob Goon",
    "Mob Role Blocker",
    "Serial Killer",
    "Jester",
    "Vigilante"
]

class TestThemesAndSkins(unittest.TestCase):
    """Verifies all 9 themes, role skin mappings, non-death narration, and prompt rubrics."""

    def test_all_nine_themes_exist_in_themes_json(self):
        """Ensure data/narration/themes.json has all 9 themes configured with atmosphere and rules."""
        path = os.path.join(os.path.dirname(__file__), '..', 'data', 'narration', 'themes.json')
        with open(path, 'r', encoding='utf-8') as f:
            themes = json.load(f)

        for theme in EXPECTED_THEMES:
            self.assertIn(theme, themes, f"Missing theme '{theme}' in themes.json")
            theme_obj = themes[theme]
            self.assertIn("description", theme_obj)
            # Ensure classic and battle_royale or direct config
            if "classic" in theme_obj:
                self.assertIn("atmosphere", theme_obj["classic"])
                self.assertIn("custom_rules", theme_obj["classic"])
                self.assertIn("writing_style", theme_obj["classic"])
            else:
                self.assertIn("atmosphere", theme_obj)

    def test_all_nine_themes_exist_in_theme_roles_json(self):
        """Ensure data/game_setup/theme_roles.json has skins for all 10 canonical roles across all 9 themes."""
        path = os.path.join(os.path.dirname(__file__), '..', 'data', 'game_setup', 'theme_roles.json')
        with open(path, 'r', encoding='utf-8') as f:
            theme_roles = json.load(f)

        for theme in EXPECTED_THEMES:
            self.assertIn(theme, theme_roles, f"Missing theme '{theme}' in theme_roles.json")
            for canonical_role in CANONICAL_ROLES:
                self.assertIn(canonical_role, theme_roles[theme], 
                              f"Role '{canonical_role}' not defined for theme '{theme}' in theme_roles.json")
                skin = theme_roles[theme][canonical_role]
                self.assertTrue(bool(skin.get("display_name")), f"Empty display_name for {canonical_role} in {theme}")
                self.assertTrue(bool(skin.get("description")), f"Empty description for {canonical_role} in {theme}")

    def test_get_role_instance_applies_theme_skin(self):
        """Ensure get_role_instance preserves mechanical role.name while skinning role.display_name."""
        # 1. Rom Com
        cop_romcom = get_role_instance("Town Cop", theme="Rom Com")
        self.assertEqual(cop_romcom.name, "Town Cop")
        self.assertEqual(cop_romcom.display_name, "Relationship Detective")
        self.assertEqual(cop_romcom.theme, "Rom Com")
        self.assertIn("Town", cop_romcom.alignment)

        # 2. Office Restructuring
        gf_office = get_role_instance("Godfather", theme="Office Restructuring")
        self.assertEqual(gf_office.name, "Godfather")
        self.assertEqual(gf_office.display_name, "Restructuring Partner")
        self.assertEqual(gf_office.theme, "Office Restructuring")

        # 3. Explicit Kinky NSFW
        sk_nsfw = get_role_instance("Serial Killer", theme="Explicit Kinky NSFW")
        self.assertEqual(sk_nsfw.name, "Serial Killer")
        self.assertEqual(sk_nsfw.display_name, "Sadistic Edge-Lord")

        # 4. Horror
        doc_horror = get_role_instance("Town Doctor", theme="Horror")
        self.assertEqual(doc_horror.name, "Town Doctor")
        self.assertEqual(doc_horror.display_name, "Camp Medic")

        # 5. Default / Classic Mafia
        citizen_classic = get_role_instance("Plain Townie", theme="Classic Mafia")
        self.assertEqual(citizen_classic.name, "Plain Townie")
        self.assertEqual(citizen_classic.display_name, "Plain Townie")

    def test_generate_game_roles_applies_game_theme(self):
        """Ensure generate_game_roles skins all distributed roles according to game.game_settings['story_type']."""
        mock_game = MagicMock()
        mock_game.game_settings = {
            "game_type": "classic",
            "story_type": "Rom Com",
            "mafia_ratio": 0.25,
            "town_rb_req": 8,
            "mafia_rb_req": 8,
            "sk_player_count": 8,
            "town_cop_req": 5,
            "town_doctor_req": 5
        }
        
        # Create 5 mock players
        players = []
        for i in range(5):
            p = MagicMock()
            p.id = 100 + i
            p.display_name = f"Player_{i}"
            p.role = None
            players.append(p)
        
        mock_game.players = players

        # Run role generation
        roles = generate_game_roles(mock_game)
        self.assertEqual(len(roles), 5)

        for r in roles:
            self.assertIsNotNone(r)
            self.assertEqual(r.theme, "Rom Com")
            self.assertIn(r.name, CANONICAL_ROLES)
            if r.name == "Town Cop":
                self.assertEqual(r.display_name, "Relationship Detective")
            elif r.name == "Godfather":
                self.assertEqual(r.display_name, "Serial Heartbreaker")
            elif r.name == "Town Doctor":
                self.assertEqual(r.display_name, "Wingman")

    def test_non_death_static_narration_rom_com(self):
        """Ensure static storyteller for Rom Com uses non-lethal breakup/ghosting terminology."""
        victim = MagicMock()
        victim.display_name = "Alice"
        victim.role = get_role_instance("Town Cop", theme="Rom Com")

        killer = MagicMock()
        killer.display_name = "Bob"
        killer.role = get_role_instance("Godfather", theme="Rom Com")

        healer = MagicMock()
        healer.display_name = "Charlie"
        healer.role = get_role_instance("Town Doctor", theme="Rom Com")

        # 1. Kill event
        kill_story = static_storyteller._generate_static_story_part(
            {'type': 'kill', 'victim': victim, 'killer': killer},
            story_type="Rom Com"
        )
        self.assertIn("dumped", kill_story.lower())
        self.assertIn("dating market", kill_story.lower())
        self.assertNotIn("murder", kill_story.lower())
        self.assertNotIn("body of", kill_story.lower())
        self.assertNotIn("corpse", kill_story.lower())

        # 2. Lynch event
        voter = MagicMock()
        voter.display_name = "Dave"
        lynch_story = static_storyteller._generate_static_story_part(
            {'type': 'lynch', 'victims': [victim], 'details': {victim: [voter]}},
            story_type="Rom Com"
        )
        self.assertIn("ghosted", lynch_story.lower())
        self.assertNotIn("strung up", lynch_story.lower())
        self.assertNotIn("lynched", lynch_story.lower())

        # 3. Save event
        save_story = static_storyteller._generate_static_story_part(
            {'type': 'save', 'victim': victim, 'healer': healer},
            story_type="Rom Com"
        )
        self.assertIn("wingman", save_story.lower())

        # 4. Block event
        block_story = static_storyteller._generate_static_story_part(
            {'type': 'block', 'target': victim},
            story_type="Rom Com"
        )
        self.assertIn("third-wheeled", block_story.lower())

        # 5. Jester win
        jester = MagicMock()
        jester.display_name = "Eve"
        jester.role = get_role_instance("Jester", theme="Rom Com")
        jester_story = static_storyteller._generate_static_story_part(
            {'type': 'jester_win', 'victim': jester},
            story_type="Rom Com"
        )
        self.assertIn("drama queen", jester_story.lower())

    def test_non_death_static_narration_office_restructuring(self):
        """Ensure static storyteller for Office Restructuring uses corporate layoff/termination terminology."""
        victim = MagicMock()
        victim.display_name = "Alice"
        victim.role = get_role_instance("Town Cop", theme="Office Restructuring")

        killer = MagicMock()
        killer.display_name = "Bob"
        killer.role = get_role_instance("Godfather", theme="Office Restructuring")

        # 1. Kill event
        kill_story = static_storyteller._generate_static_story_part(
            {'type': 'kill', 'victim': victim, 'killer': killer},
            story_type="Office Restructuring"
        )
        self.assertIn("laid off", kill_story.lower())
        self.assertNotIn("body of", kill_story.lower())
        self.assertNotIn("murder", kill_story.lower())

        # 2. Lynch event
        voter = MagicMock()
        voter.display_name = "Dave"
        lynch_story = static_storyteller._generate_static_story_part(
            {'type': 'lynch', 'victims': [victim], 'details': {victim: [voter]}},
            story_type="Office Restructuring"
        )
        self.assertIn("terminated", lynch_story.lower())
        self.assertNotIn("strung up", lynch_story.lower())
        self.assertNotIn("lynched", lynch_story.lower())

        # 3. Save event
        save_story = static_storyteller._generate_static_story_part(
            {'type': 'save', 'victim': victim},
            story_type="Office Restructuring"
        )
        self.assertIn("hr legal", save_story.lower())

        # 4. Block event
        block_story = static_storyteller._generate_static_story_part(
            {'type': 'block', 'target': victim},
            story_type="Office Restructuring"
        )
        self.assertIn("it support", block_story.lower())

    def test_ai_prompt_construction_rubrics(self):
        """Ensure _construct_ai_prompt injects non-death/theme-specific rules into the reasoning rubric."""
        living_names = ["Alice", "Bob", "Charlie"]

        # 1. Rom Com
        romcom_state = {
            "story_type": "Rom Com",
            "phase": "night",
            "number": 1,
            "players": living_names,
            "game_type": "classic"
        }
        romcom_prompt = ai_storyteller._construct_ai_prompt(romcom_state, [], [])
        self.assertIn("STRICTLY NO MURDER, NO DEATH, NO CORPSES, NO BLOOD, NO PHYSICAL VIOLENCE", romcom_prompt)
        self.assertIn("DUMPED, GHOSTED", romcom_prompt)

        # 2. Office Restructuring
        office_state = {
            "story_type": "Office Restructuring",
            "phase": "day",
            "number": 1,
            "players": living_names,
            "game_type": "classic"
        }
        office_prompt = ai_storyteller._construct_ai_prompt(office_state, [], [])
        self.assertIn("STRICTLY NO MURDER, NO DEATH, NO CORPSES, NO VIOLENCE", office_prompt)
        self.assertIn("FIRED, LAID OFF", office_prompt)

        # 3. Explicit Kinky NSFW
        nsfw_state = {
            "story_type": "Explicit Kinky NSFW",
            "phase": "night",
            "number": 1,
            "players": living_names,
            "game_type": "classic"
        }
        nsfw_prompt = ai_storyteller._construct_ai_prompt(nsfw_state, [], [])
        self.assertIn("R18 CONSENTING ADULTS", nsfw_prompt)
        self.assertIn("aftercare lounge", nsfw_prompt)

        # 4. Classic Mafia
        classic_state = {
            "story_type": "Classic Mafia",
            "phase": "night",
            "number": 1,
            "players": living_names,
            "game_type": "classic"
        }
        classic_prompt = ai_storyteller._construct_ai_prompt(classic_state, [], [])
        self.assertIn("LIVING PLAYERS ONLY", classic_prompt)
        self.assertIn("CORPSE", classic_prompt)

    def test_status_display_labels_for_non_death_themes(self):
        """Ensure get_status_message uses theme-appropriate status headers for Rom Com & Office Restructuring."""
        mock_game = MagicMock()
        mock_game.game_settings = {
            "game_id": "test_game_123",
            "current_phase": "day",
            "phase_number": 1,
            "phase_end_time": datetime.now(timezone.utc) + timedelta(minutes=10),
            "story_type": "Rom Com"
        }

        living_player = MagicMock()
        living_player.id = 1
        living_player.display_name = "Alice"
        living_player.is_alive = True
        living_player.is_winner = False
        living_player.role = get_role_instance("Town Cop", theme="Rom Com")

        elim_player = MagicMock()
        elim_player.id = 2
        elim_player.display_name = "Bob"
        elim_player.is_alive = False
        elim_player.is_winner = False
        elim_player.death_info = {"phase": "Day 1", "how": "Ghosted"}
        elim_player.role = get_role_instance("Mob Goon", theme="Rom Com")

        mock_game.players = {1: living_player, 2: elim_player}

        # 1. Rom Com status
        romcom_status = get_status_message(mock_game)
        self.assertIn("Dumped / Off Market", romcom_status)
        self.assertIn("Serial Ghoster", romcom_status)

        # 2. Office Restructuring status
        mock_game.game_settings["story_type"] = "Office Restructuring"
        living_player.role = get_role_instance("Town Cop", theme="Office Restructuring")
        elim_player.role = get_role_instance("Mob Goon", theme="Office Restructuring")
        office_status = get_status_message(mock_game)
        self.assertIn("Terminated / Former Staff", office_status)
        self.assertIn("Hatchet Associate", office_status)

        # 3. Classic Mafia status
        mock_game.game_settings["story_type"] = "Classic Mafia"
        living_player.role = get_role_instance("Town Cop", theme="Classic Mafia")
        elim_player.role = get_role_instance("Mob Goon", theme="Classic Mafia")
        classic_status = get_status_message(mock_game)
        self.assertIn("Dead Players", classic_status)

if __name__ == '__main__':
    unittest.main()
