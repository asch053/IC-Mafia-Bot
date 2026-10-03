import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

async def send_mafia_info_dm(bot, players):
    """Sends mafia members a list of their teammates."""
    mafia_players = [p for p in players.values() if p.role and p.role.alignment == "Mafia"]
    logger.debug(f"Found {len(mafia_players)} Mafia players.")
    # If no Mafia players, we can skip sending DMs
    if not mafia_players:
        logger.error("No Mafia players found to send team information.")
        return
    for player in mafia_players:
        if player.role.alignment != "Mafia":
            logger.warning(f"Player {player.display_name} does not have a Mafia role. Skipping DM.")
            continue  # Just a safety check, should not happen
        if player.id < 0:
            logger.warning(f"Skipping DM for player {player.display_name} because it's a bot.")
            continue
        try:
            user = await bot.fetch_user(player.id)
            mafia_names = ", ".join([p.display_name for p in mafia_players if p.id != player.id])
            msg = f"Your Mafia teammates are: **{mafia_names}**" if mafia_names else "You are the only Mafia member. Good luck!"
            await user.send(msg)
            logger.debug(f"Sent Mafia team info DM to {player.display_name}.")
        except Exception as e:
            logger.error(f"Failed to send mafia DM to {player.display_name}: {e}")