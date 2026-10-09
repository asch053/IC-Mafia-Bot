# game/engine/win.py
import logging
from collections import Counter
import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def check_win_conditions(game):
    """Checks if any team has won. Returns the winning team/player or None."""
    living_players = [p for p in game.players.values() if p.is_alive]
    logger.info(f"Checking win conditions for {len(living_players)} living players.")

    if not living_players:
        return "Draw"

    counts = Counter(p.role.alignment for p in living_players if p.role)
    mafia_count = counts.get("Mafia", 0)
    town_count = counts.get("Town", 0)
    neutral_killer_count = sum(
        1 for p in living_players
        if p.role and p.role.alignment == "Serial Killer" and "kill" in p.role.abilities
    )
    logger.info(f"Living counts - Mafia: {mafia_count}, Town: {town_count}, Neutral Killers: {neutral_killer_count}")

    if len(living_players) == 1:
        last_player = living_players[0]
        if last_player.role:
            logger.info(f"Win Condition Met: {last_player.display_name} is the last one standing.")
            if game.game_settings.get('game_type') == 'battle_royale':
                return last_player.display_name
            else:
                return last_player.role.alignment

    current_phase = str(game.game_settings.get("current_phase", "")).lower()
    if current_phase == "pre-day" and len(living_players) == 2 and (
        (mafia_count == 1 and town_count == 1) or
        (neutral_killer_count == 1 and town_count == 1) or
        (mafia_count == 1 and neutral_killer_count == 1)
    ):
        logger.info("Draw condition met: Only two players left, one from each alignment.")
        return "Draw"

    if game.game_settings.get("game_type") != "battle_royale":
        if mafia_count == 0 and neutral_killer_count == 0:
            if town_count > 0:
                logger.info("Win Condition Met: Town wins.")
            return "Town"

        if mafia_count == town_count and neutral_killer_count == 0 and current_phase == "pre-night":
            protective_roles = [
                p for p in living_players
                if p.role and ("heal" in p.role.abilities or "block" in p.role.abilities)
            ]
            if not protective_roles and mafia_count > 0:
                logger.info("Win Condition Met: Mafia wins.")
                return "Mafia"
            elif protective_roles:
                logger.info("Pre-night with equal numbers: Town has protective roles, continuing to night phase.")
                return None

        non_mafia_count = len(living_players) - mafia_count
        if mafia_count >= non_mafia_count and neutral_killer_count == 0:
            if mafia_count > 0:
                logger.info("Win Condition Met: Mafia wins.")
                return "Mafia"

        if neutral_killer_count > 0 and town_count == 0 and mafia_count == 0:
            logger.info("Win Condition Met: Neutral Killer wins.")
            return "Serial Killer"

        if neutral_killer_count == 1 and town_count == 1 and mafia_count == 0 and current_phase == "pre-night":
            protective_roles = [
                p for p in living_players
                if p.role and ("heal" in p.role.abilities or "block" in p.role.abilities)
            ]
            if not protective_roles:
                logger.info("Win Condition Met: Serial Killer wins.")
                return "Serial Killer"

        if neutral_killer_count == 1 and mafia_count == 1 and town_count == 0 and current_phase == "pre-night":
            mafia_roles = [p.role for p in living_players if p.role and p.role.alignment == "Mafia"]
            if len(mafia_roles) == 1 and mafia_roles[0].name != "Godfather":
                logger.info("Win Condition Met: Serial Killer wins.")
                return "Serial Killer"
            if len(mafia_roles) == 1 and mafia_roles[0].name == "Godfather":
                logger.info("Win Condition Met: Draw.")
                return "Draw"

    logger.info("No win condition met yet.")
    return None


async def announce_winner(game, winner):
    """Announces the winner, generates conclusion story, and archives summary."""
    logger.info(f"Announcing winner: {winner}")
    winning_players = []
    for player_obj in game.players.values():
        player_obj.is_winner = False
        if player_obj.role:
            if winner in ["Town", "Mafia"] and player_obj.role.alignment == winner:
                player_obj.is_winner = True
            elif player_obj.role.name == winner:
                player_obj.is_winner = True
            elif player_obj.display_name == winner:
                player_obj.is_winner = True

        if player_obj.is_winner:
            winning_players.append(player_obj)
            logger.info(f"Marked {player_obj.display_name} as a winner.")

        if not player_obj.is_winner and player_obj.is_alive:
            cur_phase = str(game.game_settings.get('current_phase', '')).lower()
            phase_num = game.game_settings.get('phase_number', 0)
            if cur_phase == 'pre-day':
                recorded_phase = f"Night {phase_num}"
            elif cur_phase == 'pre-night':
                recorded_phase = f"Day {phase_num}"
            else:
                recorded_phase = f"{cur_phase.capitalize()} {phase_num}"
            player_obj.kill(recorded_phase, "Game Over - Losing Player")
            logger.info(f"Marked losing player {player_obj.display_name} as dead.")

    await game._save_game_summary(winner)

    if winner in ["Town", "Mafia"]:
        winner_display_name = f"The {winner}"
    elif winner == "Draw":
        winner_display_name = "game has ended in a draw! No one"
    elif winning_players:
        winner_display_name = f"**{winning_players[0].display_name}**"
    else:
        winner_display_name = winner

    game.game_settings['is_epilogue'] = True
    if hasattr(game, 'narration_manager') and game.narration_manager:
        game.narration_manager.add_event('game_over', winner=f"{winner_display_name}")

    game_state = {
        "game_id": game.game_settings.get('game_id'),
        "phase": "Conclusion",
        "number": None,
        "living_players": [p for p in game.players.values() if p.is_alive],
        "game_type": game.game_settings.get('game_type', 'classic'),
        "story_type": game.game_settings.get('story_type', 'Classic Mafia'),
        "is_prologue": False,
        "is_introduction": False,
        "is_epilogue": True,
        "winner": winner if winner else "No Winner",
        "is_game_over": False
    }

    story = ""
    if hasattr(game, 'narration_manager') and game.narration_manager:
        story = await game.narration_manager.construct_story(game_state=game_state) or ""

    try:
        channel = game.bot.get_channel(getattr(config, 'STORIES_CHANNEL_ID', 0))
        if channel:
            full_message = f"**Game Over!**\n{story}"
            if len(full_message) <= 2000:
                await channel.send(full_message)
            else:
                lines = full_message.split('\n')
                chunk = ""
                for line in lines:
                    if len(chunk) + len(line) + 1 > 1900:
                        await channel.send(chunk)
                        chunk = ""
                    chunk += line + "\n"
                if chunk:
                    await channel.send(chunk)

            status_message = game.get_status_message()
            if status_message:
                if len(status_message) > 1900:
                    current_chunk = ""
                    for line in status_message.split('\n'):
                        if len(current_chunk) + len(line) + 1 > 1900:
                            await channel.send(current_chunk)
                            current_chunk = line + "\n"
                        else:
                            current_chunk += line + "\n"
                    if current_chunk:
                        await channel.send(current_chunk)
                else:
                    await channel.send(status_message)
            logger.info(f"Announced winner: {winner_display_name}.")
    except Exception as e:
        logger.error(f"Error announcing winner: {e}", exc_info=True)

