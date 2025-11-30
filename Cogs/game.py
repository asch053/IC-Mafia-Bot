# cogs/game.py
import discord
import config
import logging
from discord import app_commands
from discord.ext import commands
from game.engine import Game
from datetime import datetime, timezone
from utils import utilities
from utils.admincheck import is_admin
from datetime import datetime, timezone

# Get the logger instance from the main bot file
logger = logging.getLogger('discord')

def is_game_active(interaction: discord.Interaction) -> bool:
    """
    A global check function for slash commands to verify if a game is currently running.
    This prevents commands like /vote from being used when no game is active.
    """
    # Get the GameCog instance from the bot
    cog = interaction.client.get_cog("GameCog")
    # Return True only if the cog exists and its 'game' attribute is not None
    return cog and cog.game is not None

class GameCog(commands.Cog, name="GameCog"):
    """
    This cog manages the main gameplay commands and the lifecycle of the game instance.
    It acts as the primary interface between Discord users and the game engine.
    """
    def __init__(self, bot):
        """Initializes the GameCog, setting the game instance to None initially."""
        self.bot = bot
        self.game = None
    
    def get_game_instance(self):
        """A helper method to safely get the active game instance."""
        return self.game
    
    def _cleanup_game(self):
        """
        A callback function passed to the game engine.
        It's called when the game loop ends to reset the cog's state.
        """
        logger.info("GameCog: Cleaning up and resetting game instance after game conclusion.")
        self.game = None

    # --- Autocomplete Function ---
    async def player_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """
        An autocomplete provider for slash commands. It dynamically suggests the names
        of living players as the user types in a command option.
        """
        game = self.get_game_instance()
        if not game:
            return [] # Return no choices if there is no game running
        choices = []
        # Create a list of names for all living players
        living_players = [p.display_name for p in game.players.values() if p.is_alive]
        # Filter the list based on the user's current input (case-insensitive)
        for player_name in living_players:
            if current.lower() in player_name.lower():
                choices.append(app_commands.Choice(name=player_name, value=player_name))
        # Return the top 25 matches, as per Discord's limit
        return choices[:25]
    
    # --- Event Listener ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Handles two primary message events: 
        1. UX Redirection: Guides users to slash commands in specific channels.
        2. Chat Logging: Records messages from the designated talk channel for stats/AI.
        """
        # Ignore messages from bots and all Direct Messages (DRY Principle)
        if message.author.bot or not message.guild:
            return
        game = self.get_game_instance()
        if not game:
            # 1. UX Redirection (Even if no game, still redirect if in the signup channel)
            if message.channel.id == config.SIGN_UP_HERE_CHANNEL_ID:
                await message.reply(
                    f"Please use the slash command `/mafiajoin` to join, or discuss in <#{config.TALKY_TALKY_CHANNEL_ID}>."
                )
            return # Do nothing further if no game is running
        # --- 1. UX Redirection (Only check channels relevant during an active game) ---
        if message.channel.id == config.VOTING_CHANNEL_ID:
            # Politely redirect users trying to chat or use old prefix commands
            logger.info(f"Redirecting user {message.author.name} from chatting in voting channel.")
            await message.reply(
                f"Please do not chat in the voting channel. Use the slash command `/vote` to vote, or discuss in <#{config.TALKY_TALKY_CHANNEL_ID}>."
            )
            return # Stop processing after redirection
        
        # --- 2. Chat Logging (FR-5.4) ---
        # 2.1 Check if it's the correct discussion channel
        talk_channel_id = config.TALKY_TALKY_CHANNEL_ID # The designated discussion channel for the game
        if message.channel.id != talk_channel_id:
            return # Stop if not in the logging channel
        # 2.2 Check if a game is active and it's not the signup phase
        # Note: We ensure 'game.phase' is robustly checked against 'signup'
        if game.game_settings.get('current_phase', '').lower() == 'signup':
            return
        # 2.3 Log the message (Data structure is already great!)
        log_entry = {
            'user_id': message.author.id, # Unique Discord user ID
            'username': message.author.display_name, # For easier log reading
            'timestamp_utc': message.created_at.isoformat(), # Standardized timestamp
            'channel_name': message.channel.name, # For easier log reading
            'message_id': message.id, # Unique message identifier
            'phase': game.game_settings.get('current_phase', 'N/A'), # Log the current phase for context
            'phase_number': game.game_settings.get('phase_number', 0), # Log the phase number for context
            'content': message.content # The actual message text
        }
        # We assume the Game object has been extended with an active chat_log attribute
        game.chat_log.append(log_entry)
        logger.debug(
            f"Chat Logged: Game={game.game_settings.get('game_id')} | Phase={log_entry['phase']} | User={message.author.name}"
        )

    # --- Game Management Commands ---
    @app_commands.command(name="mafiastart", description="[Admin] Schedules a new Mafia game.")
    @app_commands.describe(
        game_type="The type of Mafia game to start (e.g., Classic, Battle Royale).",
        phase_hours="The duration of each day/night phase in hours.",
        start_datetime="The start time in 'YYYY-MM-DD HH:MM' format (UTC)."
    )
    @app_commands.choices(game_type=[
        app_commands.Choice(name="Classic", value="classic"),
        app_commands.Choice(name="Battle Royale", value="battle_royale")
    ])
    @is_admin() # Decorator: This command can only be used by admins.
    async def start_game_command(self, interaction: discord.Interaction, game_type: str, phase_hours: float, start_datetime: str):
        """Command for admins to schedule a new game."""
        logger.info(f"'/mafiastart' command invoked by {interaction.user.name} with args: type={game_type}, hours={phase_hours}, start='{start_datetime}'.")
        # Prevent starting a game if one is already running
        if self.game is not None:
            await interaction.response.send_message("A game is already in progress!", ephemeral=True)
            return
        # Validate the date and time format provided by the admin
        logger.error(f"Validating start date/time: '{start_datetime}'.")    
        try:
            start_datetime_obj = datetime.strptime(start_datetime, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            await interaction.response.send_message("Invalid date/time format. Please use 'YYYY-MM-DD HH:MM' format in UTC.", ephemeral=True)
            return
        # Ensure the start time is in the future to prevent immediate, accidental starts
        if start_datetime_obj <= datetime.now(timezone.utc):
            await interaction.response.send_message("The start time must be in the future.", ephemeral=True)
            return
        # Acknowledge the command while the bot prepares the game announcement
        await interaction.response.defer(ephemeral=True)
        # Create a new Game instance and store it in the cog
        self.game = Game(self.bot, interaction.guild, cleanup_callback=self._cleanup_game)
        logger.info(f"New game instance created by admin: {interaction.user.name}.")
        # Confirm to the admin that the game has been scheduled successfully
        await interaction.followup.send(f"Game scheduled by {interaction.user.mention}!", ephemeral=True)
        # Call the game engine's start method to begin the sign-up phase
        await self.game.start(game_type, start_datetime_obj, phase_hours)

    # --- Player Commands (Channel) ---
    @app_commands.command(name="mafiajoin", description="Joins the current game during the sign-up phase.")
    async def join_game_command(self, interaction: discord.Interaction):
        """Allows a player to join an active game during sign-ups."""
        logger.info(f"'/mafiajoin' command invoked by {interaction.user.name}.")
        if self.game is None or self.game.game_settings["current_phase"] != "signup":
            await interaction.response.send_message("No game is currently accepting sign-ups.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        # Delegate the actual player-adding logic to the game engine
        await self.game.add_player(interaction.user, interaction.user.display_name, interaction.channel)
        await interaction.followup.send("You've joined the game!", ephemeral=True)

    @app_commands.command(name="mafialeave", description="Leave the game during the sign-up phase.")
    async def leave_game_command(self, interaction: discord.Interaction):
        """Allows a player to leave the game during sign-ups."""
        logger.info(f"'/mafialeave' command invoked by {interaction.user.name}.")
        if self.game is None or self.game.game_settings["current_phase"] != "signup":
            await interaction.response.send_message("There is no game to leave, or sign-ups are closed.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        # Delegate the logic to the game engine
        await self.game.remove_player(interaction.user, interaction.channel)
        await interaction.followup.send("You've left the game.", ephemeral=True)

    @app_commands.command(name="mafiastatus", description="Displays the current game status.")
    # @app_commands.check(is_game_active) # Check: Only works if a game is running.
    async def status_command(self, interaction: discord.Interaction):
        """Displays a public summary of the game state (living/dead players)."""
        logger.info(f"'/mafiastatus' command invoked by {interaction.user.name}.")
        # --- CHECK for active game ---
        # Access the game instance (adjust 'GameCog' if your cog name is different)
        game_cog = self.bot.get_cog("GameCog") 
        if not game_cog or not game_cog.game or not game_cog.game.game_settings["game_started"]:
            await interaction.response.send_message("❌ There is no game currently running.", ephemeral=True)
            return
        # ------------------------
        status_message = self.game.get_status_message()
        await interaction.response.send_message(status_message, ephemeral=False)

    @app_commands.command(name="vote", description="Vote to lynch a player during the day.")
    @app_commands.describe(player="The player you want to lynch.")
    @app_commands.autocomplete(player=player_autocomplete) # Autocomplete: Suggests living players.
    @app_commands.check(is_game_active) # Check: Only works if a game is running.
    async def vote(self, interaction: discord.Interaction, player: str):
        """Processes a player's vote during the day phase."""
        logger.info(f"'/vote' command invoked by {interaction.user.name}, targeting '{player}'.")
        await interaction.response.defer(ephemeral=True)
        # The game engine handles all validation and state changes
        message = await self.game.process_lynch_vote(interaction, interaction.user, player)
        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(name="mafiacount", description="Displays the current vote tally.")
    @app_commands.check(is_game_active) # Check: Only works if a game is running.
    async def count_votes_command(self, interaction: discord.Interaction):
        """Publicly displays the current vote count."""
        logger.info(f"'/mafiacount' command invoked by {interaction.user.name}.")
        await self.game.send_vote_count(interaction.channel)
        # Send a small, ephemeral confirmation so Discord doesn't think the command failed
        await interaction.response.send_message("Vote count displayed.", ephemeral=True)
    
    # --- Player Commands (DM) ---
    @app_commands.command(name="myrole", description="[DM Only] Resends your current role information.")
    @app_commands.check(is_game_active) # Check: Only works if a game is running.
    async def myrole_command(self, interaction: discord.Interaction):
        """Allows a player to have their role card resent in a DM."""
        logger.info(f"'/myrole' command invoked by {interaction.user.name} in DMs.")
        # Ensure the command is used in a DM, not in a server channel
        if interaction.guild:
            await interaction.response.send_message("This command can only be used in DMs.", ephemeral=True)
            return
        # Safely get the game instance and the player object
        game = self.get_game_instance()
        player_obj = game.players.get(interaction.user.id)
        if not player_obj or not player_obj.role:
            await interaction.response.send_message("You are not in the game or have no role.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        # Use the utility function to handle the complexities of sending a DM
        success = await utilities.send_role_dm(self.bot, player_obj.id, player_obj.role, game.guild)
        if success:
            await interaction.followup.send("Your role information has been resent.", ephemeral=True)
        else:
            await interaction.followup.send("I was unable to resend your role. Please check your privacy settings.", ephemeral=True)

    # --- Night Action Commands (DM Only) ---
    async def _handle_night_action(self, interaction: discord.Interaction, action_type: str, target_name: str):
        """
        A generic handler for all night actions to reduce code duplication.
        It performs initial checks and then passes the action to the game engine.
        """
        logger.info(f"Handling night action '{action_type}' from {interaction.user.name} on target '{target_name}'.")
        if not is_game_active(interaction):
            await interaction.response.send_message("No game is currently running.", ephemeral=True)
            return
        # Ensure night actions are only used in DMs where they are secret
        if interaction.guild:
            await interaction.response.send_message("Night actions must be used in DMs.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=False)
        # The game engine handles all the complex logic (role checks, timing, etc.)
        message = await self.game.record_night_action(interaction, action_type, target_name)
        await interaction.followup.send(message, ephemeral=False)

    @app_commands.command(name="kill", description="[DM Only] Action for roles that can kill.")
    @app_commands.describe(player="The player you want to kill.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def kill(self, interaction: discord.Interaction, player: str):
        """Kill command, delegates to the generic action handler."""
        await self._handle_night_action(interaction, 'kill', player)
        
    @app_commands.command(name="heal", description="[DM Only] Action for the Doctor to heal a player.")
    @app_commands.describe(player="The player you want to heal.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def heal(self, interaction: discord.Interaction, player: str):
        """Heal command, delegates to the generic action handler."""
        await self._handle_night_action(interaction, 'heal', player)
    
    @app_commands.command(name="investigate", description="[DM Only] Action for the Cop to investigate a player.")
    @app_commands.describe(player="The player you want to investigate.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def investigate(self, interaction: discord.Interaction, player: str):
        """Investigate command, delegates to the generic action handler."""
        await self._handle_night_action(interaction, 'investigate', player)

    @app_commands.command(name="block", description="[DM Only] Action for the Role Blocker to block an action.")
    @app_commands.describe(player="The player you want to block.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def block(self, interaction: discord.Interaction, player: str):
        """Block command, delegates to the generic action handler."""
        await self._handle_night_action(interaction, 'block', player)

async def setup(bot):
    """The setup function required by discord.py to load the cog."""
    await bot.add_cog(GameCog(bot))
    logger.info("GameCog loaded.")

