import logging
import discord
import config
from game.player import Player

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def reinitialize_players_command(self, interaction: discord.Interaction):
    """
    A powerful debug command to rebuild the game's internal player list
    based on which server members have the 'Living' or 'Dead' roles.
    """
    logger.info(f"'/mafiareinit' command invoked by {interaction.user.name}.")
    game = self.get_game_instance()
    if game is None:
        await interaction.response.send_message("No game is running to re-initialize.", ephemeral=True)
        return
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    living_role = interaction.guild.get_role(getattr(config, 'LIVING_ROLE_ID', 0))
    dead_role = interaction.guild.get_role(getattr(config, 'DEAD_ROLE_ID', 0))

    try:
        if not living_role or not dead_role:
            await interaction.response.send_message("Error: 'Living' or 'Dead' roles not found.", ephemeral=True)
            return
    except Exception as e:
        logger.error(f"Error occurred while fetching roles: {e}")
        await interaction.response.send_message("An error occurred while fetching roles.", ephemeral=True)
        return

    logger.info("Rebuilding internal player list from server roles...")
    new_players = {}
    for member in interaction.guild.members:
        if living_role in member.roles or dead_role in member.roles:
            old_player = game.players.get(member.id)
            new_player = Player(user_id=member.id, discord_name=member.name, display_name=member.display_name)
            new_player.is_alive = living_role in member.roles
            if old_player:
                new_player.role = old_player.role
                new_player.death_info = old_player.death_info
            new_players[member.id] = new_player

    game.players = new_players
    await interaction.response.send_message(f"Player list re-initialized. Found {len(new_players)} players.", ephemeral=True)
    logger.warning(f"Player list was manually re-initialized by admin: {interaction.user.name}.")

