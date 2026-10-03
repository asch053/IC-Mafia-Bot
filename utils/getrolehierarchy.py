import logging
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_role_hierarchy(roles: list, current_user_role: discord.Role) -> bool:
    """Checks if the current user's highest role is higher than all target roles."""
    logger.debug(f"Checking role hierarchy for user role: {current_user_role.name} against target roles: {[role.name for role in roles if role]}.")
    for role in roles:
        if role and role.position >= current_user_role.position:
            logger.debug(f"Role hierarchy violation: User role '{current_user_role.name}' is not higher than target role '{role.name}'.")
            return False
        logger.debug(f"User role '{current_user_role.name}' is higher than target role '{role.name}'.")
    return True