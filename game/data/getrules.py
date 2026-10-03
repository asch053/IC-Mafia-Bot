# game/data/getrules.py
import json
import logging
import os
from datetime import datetime
import discord
from utils.loaddata import load_data
from utils.addchunkedfield import add_chunked_field

# Get the same logger instance as in bot setup
logger = logging.getLogger('discord')


def format_discord_time(dt_input):
    """Converts a datetime or ISO string into Discord's native dynamic timestamp syntax."""
    if not dt_input or dt_input == 'Unknown':
        return "TBD"
    if isinstance(dt_input, str):
        try:
            dt = datetime.fromisoformat(dt_input.replace('Z', '+00:00'))
        except Exception:
            return dt_input
    elif isinstance(dt_input, datetime):
        dt = dt_input
    else:
        return str(dt_input)
    
    epoch = int(dt.timestamp())
    return f"<t:{epoch}:F> (<t:{epoch}:R>)"


def create_header(self, game_settings):
    """Creates a clean, formatted header for the rules embed based on game settings."""
    game_type = str(game_settings.get('game_type', 'Classic')).replace('_', ' ').title()
    story_type = game_settings.get('story_type', 'Classic Mafia')
    raw_start = game_settings.get('start_time', 'Unknown')
    formatted_start = format_discord_time(raw_start)

    header = (
        f"🎮 **Game Type:** {game_type}\n"
        f"📖 **Story Theme:** {story_type}\n"
        f"⏳ **Start Time:** {formatted_start}\n"
    )
    logger.info("Header created successfully.")
    return header


def load_static_rules(self):
    """Reads the static rules from data/game_setup/rules.txt and returns them as a string."""
    try:
        static_rules = load_data("data/game_setup/rules.txt")
        if isinstance(static_rules, list):
            rules_text = "\n".join(static_rules)
        else:
            rules_text = str(static_rules)
        logger.info("Static rules loaded successfully.")
    except Exception as e:
        logger.error(f"Error loading static rules: {e}")
        rules_text = (
            "1. **Fair Play & Fun:** Respect all players. No toxicity.\n"
            "2. **No Meta-Gaming:** Do not discuss the game outside designated channels.\n"
            "3. **Secret Intel:** Never share screenshots or role messages.\n"
            "4. **Daytime Voting:** Discuss and vote to lynch using `/vote @player`.\n"
            "5. **Night Actions:** Submit secret abilities via bot DM.\n"
            "6. **Activity:** Missing consecutive votes results in inactivity elimination."
        )

    return rules_text


def get_dynamic_rules(self, game_settings):
    """Creates formatted dynamic setup parameters with clean Discord blockquote styling."""
    game_type = str(game_settings.get('game_type', 'classic')).lower()
    gf_investigate = game_settings.get('gf_investigate', True)
    sk_investigate = game_settings.get('sk_investigate', False)
    gf_night_immune = game_settings.get('gf_night_immune', True)
    sk_night_immune = game_settings.get('sk_night_immune', True)
    phase_length = game_settings.get('phase_hours', 12)
    mafia_ratio = int(game_settings.get('mafia_ratio', 0.25) * 100)
    sk_min = game_settings.get("sk_player_count", 9)
    town_rb_req = game_settings.get('town_rb_req', 10)
    town_cop_req = game_settings.get('town_cop_req', 6)
    town_doctor_req = game_settings.get('town_doctor_req', 7)
    mafia_req = game_settings.get('mafia_rb_req', 4)

    if game_type == "battle_royale":
        skip_day = game_settings.get('br_skip_day', False)
        dynamic_setup = (
            f"> ⏱️ **Phase Length:** {phase_length} Hours\n"
            f"> ⚔️ **Mode Rules:** Free-for-all survival; no factions.\n"
            f"> 🌙 **Day Phase:** {'Skipped (consecutive night action phases only)' if skip_day else 'Enabled (standard day/night cycle)'}"
        )
    else:
        dynamic_setup = (
            f"> ⏱️ **Phase Length:** {phase_length} Hours\n"
            f"> ⚖️ **Mafia Ratio:** {mafia_ratio}%\n"
            f"> 🔪 **Serial Killer:** Spawns at {sk_min}+ Players\n"
            f"> 🛡️ **Town Roles:** Cop ({town_cop_req}+), Doctor ({town_doctor_req}+), Roleblocker ({town_rb_req}+)\n"
            f"> 🦹 **Mafia Roles:** Goons, and Roleblocker at {mafia_req} Mafia members\n"
            f"> 🕵️ **Investigations:** Godfather is {'detectable' if gf_investigate else 'hidden (appears Town)'}, Serial Killer is {'detectable' if sk_investigate else 'hidden'}\n"
            f"> 🛡️ **Night Immunity:** Godfather is {'immune' if gf_night_immune else 'vulnerable'}, Serial Killer is {'immune' if sk_night_immune else 'vulnerable'}"
        )

    logger.info("Dynamic rules generated successfully.")
    return dynamic_setup


def game_type_rules(self, game_type):
    """Returns clean bulleted objectives based on game type without number collisions."""
    gt = str(game_type).lower() if game_type else "classic"
    logger.info(f"Generating objectives for game type: {gt}")
    if gt == "battle_royale":
        return (
            "• **Free-For-All:** Every player fights for individual survival.\n"
            "• **Night Phase:** Each night, you will either receive an offensive or defensive action.\n"
            "• **Victory:** The last surviving player wins."
        )
    else:
        return (
            "• **Town:** Identify and lynch all Mafia members and hostile third parties.\n"
            "• **Mafia:** Eliminate Town until achieving parity or numerical superiority.\n"
            "• **Serial Killer:** Outlast all other factions and be the last player standing.\n"
            "• **Night Actions:** Mafia and Serial Killer submit night kills. Town power roles protect, investigate, or block."
        )


def build_rules_embed(self, game=None):
    """Standalone helper to build the polished rules embed for /mafiarules or game start."""
    logger.info("Building rules embed with header and dynamic content.")
    embed = discord.Embed(
        title="📜 Mafia Game Protocol",
        description="*Welcome to Imperial Conflict Mafia. Review the protocol and prepare for battle.*",
        color=discord.Color.red()
    )

    settings = game.game_settings if game and hasattr(game, 'game_settings') else {}
    header = create_header(self, settings)
    rules_content = load_static_rules(self)
    setup_info = get_dynamic_rules(self, settings)
    game_type_info = game_type_rules(self, settings.get("game_type", "classic"))

    chunk_size = 900
    add_chunked_field(embed, "📋 Match Overview", header, chunk_size)
    add_chunked_field(embed, "⚖️ Server Rules & Conduct", rules_content, chunk_size)
    add_chunked_field(embed, "⚙️ Game Configuration", setup_info, chunk_size)
    add_chunked_field(embed, "🎯 Faction Objectives", game_type_info, chunk_size)

    embed.set_footer(text="IC Mafia Bot • Good luck and trust no one.")
    logger.info("Rules embed built successfully.")
    return embed


# Backwards compatibility alias
get_rules = build_rules_embed
create_rules_embed = build_rules_embed