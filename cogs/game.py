# cogs/game.py
import logging
import discord
from discord import app_commands
from discord.ext import commands

from cogs.gamecogs.autocomplete import player_autocomplete
from cogs.gamecogs.join import join_game_command
from cogs.gamecogs.leave import leave_game_command
from cogs.gamecogs.status import status_command
from cogs.gamecogs.vote import vote_command
from cogs.gamecogs.count import count_votes_command
from cogs.gamecogs.myrole import myrole_command
from cogs.gamecogs.nightactions import handle_night_action
from cogs.gamecogs.listener import handle_on_message

logger = logging.getLogger('discord')


def is_game_active(interaction: discord.Interaction) -> bool:
    """Checks if a game is currently running."""
    game = getattr(interaction.client, 'game_instance', None)
    if game is not None:
        return True
    cog = interaction.client.get_cog("GameCog")
    return bool(cog and getattr(cog, 'game', None))


class GameCog(commands.Cog, name="GameCog"):
    """
    Manages the main gameplay commands and acts as the interface
    between Discord users and the game engine.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def game(self):
        return getattr(self.bot, 'game_instance', None)

    @game.setter
    def game(self, value):
        self.bot.game_instance = value

    def get_game_instance(self):
        return getattr(self.bot, 'game_instance', None)

    def _cleanup_game(self):
        logger.info("GameCog: Cleaning up and resetting game instance after game conclusion.")
        self.bot.game_instance = None

    async def player_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await player_autocomplete(self, interaction, current)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await handle_on_message(self, message)

    @app_commands.command(name="mafiajoin", description="Join an upcoming Mafia game during sign-ups.")
    async def mafiajoin(self, interaction: discord.Interaction):
        await join_game_command(self, interaction)

    @app_commands.command(name="mafialeave", description="Leave the game during the sign-up phase.")
    async def mafialeave(self, interaction: discord.Interaction):
        await leave_game_command(self, interaction)

    @app_commands.command(name="mafiastatus", description="Displays the current game status.")
    async def mafiastatus(self, interaction: discord.Interaction):
        await status_command(self, interaction)

    @app_commands.command(name="vote", description="Vote to lynch a player during the day.")
    @app_commands.describe(player="The player you want to lynch.")
    @app_commands.autocomplete(player=player_autocomplete)
    @app_commands.check(is_game_active)
    async def vote(self, interaction: discord.Interaction, player: str):
        await vote_command(self, interaction, player)

    @app_commands.command(name="mafiacount", description="Displays the current vote tally.")
    @app_commands.check(is_game_active)
    async def mafiacount(self, interaction: discord.Interaction):
        await count_votes_command(self, interaction)

    @app_commands.command(name="myrole", description="[DM Only] Resends your current role information.")
    @app_commands.check(is_game_active)
    async def myrole(self, interaction: discord.Interaction):
        await myrole_command(self, interaction)

    @app_commands.command(name="kill", description="[DM Only] Action for roles that can kill.")
    @app_commands.describe(player="The player you want to kill.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def kill(self, interaction: discord.Interaction, player: str):
        await handle_night_action(self, interaction, 'kill', player)

    @app_commands.command(name="heal", description="[DM Only] Action for the Doctor to heal a player.")
    @app_commands.describe(player="The player you want to heal.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def heal(self, interaction: discord.Interaction, player: str):
        await handle_night_action(self, interaction, 'heal', player)

    @app_commands.command(name="investigate", description="[DM Only] Action for the Cop to investigate a player.")
    @app_commands.describe(player="The player you want to investigate.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def investigate(self, interaction: discord.Interaction, player: str):
        await handle_night_action(self, interaction, 'investigate', player)

    @app_commands.command(name="block", description="[DM Only] Action for the Role Blocker to block an action.")
    @app_commands.describe(player="The player you want to block.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def block(self, interaction: discord.Interaction, player: str):
        await handle_night_action(self, interaction, 'block', player)


async def setup(bot: commands.Bot):
    """The setup function required by discord.py to load the cog."""
    await bot.add_cog(GameCog(bot))
    logger.info("GameCog loaded.")

