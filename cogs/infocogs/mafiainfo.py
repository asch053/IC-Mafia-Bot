# cogs/infocogs/mafiainfo.py
import logging
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def show_info_command(self, interaction: discord.Interaction):
    """Displays a comprehensive list of all bot commands."""
    logger.info(f"'/mafiainfo' command invoked by {interaction.user.name}.")
    embed = discord.Embed(title="ℹ️ Mafia Bot Commands", color=discord.Color.green())
    player_commands = (
        "`/mafiajoin` - Join the game during sign-ups.\n"
        "`/mafialeave` - Leave the game during sign-ups.\n"
        "`/mafiastatus` - See the current game status (living/dead players).\n"
        "`/vote` - Vote to lynch a player during the day.\n"
        "`/mafiacount` - See the current vote tally.\n"
        "`/myrole` - (DM Only) Have your role resent to you.\n"
        "`/mafiarules` - Read the game rules.\n"
        "`/mafiaroles` - See roles in the current game (with alive/total counts).\n"
        "`/gamestats` - View statistics from all completed games.\n"
        "`/playerstats` - View any player's game statistics.\n"
        "`/skillscore` - View your (or another player's) skill score.\n" 
        "`/hall_of_records` - View the all time mafia records and top category holders (classic only).\n"
        "`/leaderboard` - View the current leaderboard rankings based on skill score, survival rate, or red shirt (death rate) (classic only).\n"
    )
    embed.add_field(name="Player Commands", value=player_commands, inline=False)
    action_commands = (
        "`/kill` - (DM Only) Target a player to kill at night.\n"
        "`/heal` - (DM Only) Target a player to protect at night.\n"
        "`/investigate` - (DM Only) Target a player to investigate.\n"
        "`/block` - (DM Only) Target a player to block at night."
    )
    embed.add_field(name="Night Actions", value=action_commands, inline=False)
    admin_commands = (
        "`/mafiastart` - Schedule a new game.\n"
        "`/mafiastop` - Forcibly end the current game.\n"
        "`/forcestart` - End sign-ups and start the game now.\n"
        "`/forcephaseend` - Forcibly end the current Day or Night phase.\n"
        "`/mafiareinit` - (Debug) Rebuild player list from roles.\n"
        "`/exportdata` - Export all game data to google sheets for use in website."
    )
    embed.add_field(name="Admin Commands", value=admin_commands, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    logger.info(f"Successfully sent command list to {interaction.user.name}.")

