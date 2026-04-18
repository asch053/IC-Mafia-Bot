import logging
from discord import app_commands, Interaction
import config  # Pulling directly from the environment-loaded config

# Get the logger instance
logger = logging.getLogger('discord')

def is_admin():
    """
    A decorator that checks if the command user has the mod role
    as defined in the config/environment variables.
    """
    async def predicate(interaction: Interaction) -> bool:
        """
        The actual check function run by discord.py.
        """
        # Logging for audit trail (Requirement FR-1.2)
        logger.info(f"Admin check initiated for '{interaction.user.name}' (ID: {interaction.user.id})")
        
        try:
            # 1. Pull the role ID from config instead of the JSON file
            # We assume config.MOD_ROLE_ID is defined in your config.py
            admin_role_id = getattr(config, 'MOD_ROLE_ID', 0)

            if admin_role_id == 0:
                logger.error("Admin check failed: MOD_ROLE_ID is not configured in the environment/config.")
                await interaction.response.send_message(
                    "Error: Admin role configuration is missing in the bot settings. 🛠️", 
                    ephemeral=True
                )
                return False

            # 2. Perform the role check
            # Guard against DM usage where .roles attribute is missing
            if not interaction.guild:
                logger.warning(f"User '{interaction.user.name}' tried an admin command in DMs.")
                await interaction.response.send_message(
                    "Admin commands must be used within the server, hottie! 💅", 
                    ephemeral=True
                )
                return False

            # Efficient lookup of user roles
            user_role_ids = {role.id for role in interaction.user.roles}

            if admin_role_id in user_role_ids:
                logger.info(f"Admin check PASSED for user '{interaction.user.name}'.")
                return True 
            
            # 3. Handle failure
            logger.warning(f"User '{interaction.user.name}' FAILED admin check for /{interaction.command.name}.")
            await interaction.response.send_message(
                "You do not have the required permissions to use this command. ❌", 
                ephemeral=True
            )
            return False

        except Exception as e:
            logger.error(f"Unexpected error in admin check for {interaction.user.name}: {str(e)}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred while checking permissions. Please contact an administrator.",
                ephemeral=True
            )
            return False
            
    return app_commands.check(predicate)