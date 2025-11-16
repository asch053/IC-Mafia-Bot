# utils/checks.py
import logging
from discord import app_commands, Interaction
from utils import utilities # Use a relative import within the same package

# Get the logger instance from the main bot file
logger = logging.getLogger('discord')

def is_admin():
    """
    A decorator that checks if the command user has the admin role
    as defined in the discord_roles.json file. This is used to protect
    sensitive commands from being used by regular players.
    """
    async def predicate(interaction: Interaction) -> bool:
        """
        The actual check function that is run by discord.py when a command
        with this decorator is invoked.
        """
        # Log the initiation of the admin check for traceability
        logger.info(f"Initiating admin check for user '{interaction.user.name}' for command '/{interaction.command.name}'.")
        
        try:
            # We use our lovely utility function to load the roles data
            discord_role_data = utilities.load_data("data/discord_roles.json")
            if not discord_role_data:
                logger.error("Admin check failed: Could not load discord_roles.json")
                await interaction.response.send_message("Error: Role configuration file is missing.", ephemeral=True)
                return False

            # Safely retrieve the admin role ID from the loaded data
            admin_role_id = discord_role_data.get("mod", {}).get("id", 0)
            if not admin_role_id:
                logger.error("Admin check failed: 'mod' role ID not found in discord_roles.json")
                await interaction.response.send_message("Error: Admin role is not configured.", ephemeral=True)
                return False

            # Using a set for an efficient 'in' check to see if the user has the role
            user_role_ids = {role.id for role in interaction.user.roles}

            # The core permission check
            if admin_role_id in user_role_ids:
                logger.info(f"Admin check PASSED for user '{interaction.user.name}'.")
                return True # The user is an admin!
            else:
                # If they fail the check, send a quiet, private message and log it.
                logger.warning(f"User '{interaction.user.name}' FAILED admin check for command '/{interaction.command.name}'.")
                await interaction.response.send_message(
                    "You do not have the required permissions to use this command.", 
                    ephemeral=True
                )
                return False
        except Exception as e:
            # Catch any other unexpected errors during the check
            logger.error(f"An unexpected error occurred during the admin permission check for {interaction.user.name}: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while checking your permissions. Please contact a server administrator.",
                ephemeral=True
            )
            return False
            
    # Return the check created by the app_commands library
    return app_commands.check(predicate)

