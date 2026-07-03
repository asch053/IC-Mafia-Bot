#version 1.0.4
import json
import logging
import os
import discord

import utils.utilities as utils


# Get the same logger instance as in mafiabot.py
logger = logging.getLogger('discord')

def create_header(self, game_settings):
        """
        Creates a header for the rules embed based on the game settings.
        """
        game_type = game_settings.get('game_type', 'Classic')
        story_type = game_settings.get('story_type', 'None')
        start_time = game_settings.get('start_time', 'Unknown')

        header = (
            f"**Game Type:** {game_type}\n"
            f"**Story Type:** {story_type}\n"
            f"**Start Time:** {start_time}\n"
        )
        logger.info("Header created successfully.")
        return header

def load_static_rules(self):
        """
        Reads the static rules from a text file and returns them as a string.
        """
      # 1. Read the static fallback rules
        try:
            static_rules = utils.load_data("data/game_setup/rules.txt")
            static_rules = "\n".join(static_rules) if static_rules else "Standard Mafia rules apply."
            logger.info("Static rules loaded successfully.")
        except FileNotFoundError:
            static_rules = "Standard Mafia rules apply."
            logger.error("Static rules file not found. Using default rules.")

        return static_rules

def get_dynamic_rules(self, game_settings):
        """
       Creates the dynamic setup parameters.
        """

        # 1. Extract settings with safe defaults!
        game_id = game_settings.get('game_id', 'Unknown')
        game_type = game_settings.get('game_type', 'Unknown')
        story_type = game_settings.get('story_type', 'Unknown')
        start_time = game_settings.get('start_time', 'Unknown')
        gf_investigate = game_settings.get('gf_investigate', False)
        sk_investigate = game_settings.get('sk_investigate', False)
        gf_night_immune = game_settings.get('gf_night_immune', True)
        sk_night_immune = game_settings.get('sk_night_immune', True)
        phase_length = game_settings.get('phase_hours', 12)
        mafia_ratio = int(game_settings.get('mafia_ratio', 0.25) * 100)
        sk_min = game_settings.get("sk_player_count", 10) # Set your actual SK minimum here!
        town_rb__req = game_settings.get('town_rb_req', 1)
        town_cop_req = game_settings.get('town_cop_req', 1)
        town_doctor_req = game_settings.get('town_doctor_req', 1)
        mafia_req = game_settings.get('mafia_rb_req', 1)

    
        # 2. Construct the dynamic setup block
        if game_type == "battle_royale":
              dynamic_setup = (
                f"**🎲 Current Game Setup**\n"
                f"- ⏱️ **Phase Length:** {phase_length} Hours\n"
              )
        else:
            dynamic_setup = (
                f"**🎲 Current Game Setup**\n"
                f"- ⏱️ **Phase Length:** {phase_length} Hours\n"
                f"- ⚖️ **Mafia Ratio:** {mafia_ratio}%\n"
                f"- 🔪 **Serial Killer:** Spawns at {sk_min}+ Players\n"
                f"- 🛡️ **Town Roles:** Spawn at {town_cop_req} players for Cop, {town_doctor_req} players for Doctor, and {town_rb__req} players for Roleblocker\n"
                f"- 🕴️ **Mafia Roles:** Goons, and spawn a Roleblocker with {mafia_req} mafia members\n"
                f"- 🕵️‍♂️ **Investigations:** The Godfather {'is' if gf_investigate else 'is not'} investigatable, and the Serial Killer {'is' if sk_investigate else 'is not'} investigatable\n"
                f"- 🛡️ **Night Immunity:** The Godfather {'is' if gf_night_immune else 'is not'} night immune, and the Serial Killer {'is' if sk_night_immune else 'is not'} night immune\n"
            )

        # 5. Stitch them together
        logger.info("Dynamic rules generated successfully.")
        return dynamic_setup

def game_type_rules(self, game_type):
        """
        Returns additional rules based on the game type.
        """
        logger.info(f"Generating rules for game type: {game_type}")
        if game_type == "battle_royale":
            return (
                "- **Objective:** Be the last player alive!\n"
                "- **Night Phase:** Each night, you will either have a kill action or a block action. "
                "- **Teams:** There are no teams in Battle Royale; everyone is out for themselves!"
            )
        else:
            return (
                "11. **Objective:** The Town must eliminate all Mafia members and the Serial Killer. "
                "The Mafia must outnumber the Town. The Serial Killer must be the last player standing.\n"
                "12. **Night Phase:** Mafia members choose a player to kill. The Serial Killer also chooses a player to kill. "
                "Some Town roles may have night actions."
            )


def build_rules_embed(self, game=None):
        """
        Standalone helper to build the rules embed.
        Can be called by /mafiarules or by the game engine directly.
        """
        logger.info("Building rules embed with header and dynamic content.")
        # Create the embed
        embed = discord.Embed(
            title="📜 Mafia Game Protocol",
            description="The rules are absolute.",
            color=discord.Color.red()
        )

        # Add the rules content to the embed
        header = create_header(self, game.game_settings if game else {})
        logger.info(f"Header created: {header}")
        rules_content = load_static_rules(self)
        logger.info(f"Static rules loaded: {rules_content}")
        setup_info = get_dynamic_rules(self,game.game_settings if game else {})
        logger.info(f"Dynamic setup info generated: {setup_info}")
        game_type_info = game_type_rules(self, game.game_settings["game_type"] if game else "")
        logger.info(f"Game type specific rules generated: {game_type_info}")
        chunk_size = 909  # Discord's character limit for embed fields
        #use the utility function to add chunked fields to the embed
        utils.add_chunked_field(embed, "Game Header", header, chunk_size)
        utils.add_chunked_field(embed, "Rules", rules_content, chunk_size)
        utils.add_chunked_field(embed, "Dynamic Setup", setup_info, chunk_size)
        utils.add_chunked_field(embed, "Game Type", game_type_info, chunk_size)      
        # Logging the successful creation of the embed
        logger.info("Rules embed built successfully.")
        # return the embed
        return embed