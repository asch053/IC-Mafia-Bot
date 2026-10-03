# game/engine/voting.py
import logging
from datetime import datetime, timezone
import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def process_lynch_vote(game, interaction, voter_user, target_name):
    """Processes a single vote to lynch a player, sent from a cog."""
    async with game.vote_lock:
        logger.info(f"Processing lynch vote from {voter_user.name} for target '{target_name}'")

        if game.game_settings.get("current_phase") != "day":
            logger.warning(f"{voter_user.name} tried to vote outside of the day phase.")
            return "You can only vote during the day phase."

        voter_obj = game.players.get(voter_user.id)
        if not voter_obj or not voter_obj.is_alive:
            logger.warning(f"{voter_user.name} tried to vote but is not a valid player or is dead.")
            return "You are not currently able to vote in this game."

        target_obj = game.get_player_by_name(target_name)
        if not target_obj:
            logger.warning(f"{voter_obj.display_name} tried to vote for non-existent player: {target_name}.")
            return f"Could not find a player named '{target_name}'."

        if not target_obj.is_alive:
            logger.warning(f"{voter_obj.display_name} tried to vote for dead player: {target_obj.display_name}.")
            return f"**{target_obj.display_name}** is already dead and cannot be voted for."

        # Handle vote changes
        if voter_obj.action_target is not None:
            previous_target_id = voter_obj.action_target
            if previous_target_id in game.lynch_votes and voter_obj.id in game.lynch_votes[previous_target_id]:
                game.lynch_votes[previous_target_id].remove(voter_obj.id)
                if not game.lynch_votes[previous_target_id]:
                    del game.lynch_votes[previous_target_id]

        voter_obj.action_target = target_obj.id
        game.lynch_votes.setdefault(target_obj.id, [])
        if voter_obj.id not in game.lynch_votes[target_obj.id]:
            game.lynch_votes[target_obj.id].append(voter_obj.id)

        game.vote_history.append({
            "voter_id": voter_obj.id,
            "voter_name": voter_obj.display_name,
            "target_id": target_obj.id,
            "target_name": target_obj.display_name,
            "phase": f"Day {game.game_settings.get('phase_number')}",
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        })

        voting_channel = game.bot.get_channel(getattr(config, 'VOTING_CHANNEL_ID', 0))
        if voting_channel:
            await voting_channel.send(f"**{voter_obj.display_name}** has voted for **{target_obj.display_name}**.")
            await game.send_vote_count(voting_channel)
            return f"Your vote for **{target_obj.display_name}** has been recorded."
        else:
            return "Vote recorded, but could not find the voting channel to post an update."


async def send_vote_count(game, channel):
    """Constructs and sends the current vote tally to the specified channel."""
    if not game.lynch_votes:
        await channel.send("No votes have been cast yet.")
        return

    count_message = "**Current Vote Tally:**\n"
    vote_data = sorted(game.lynch_votes.items(), key=lambda item: len(item[1]), reverse=True)
    for target_id, voter_ids in vote_data:
        target_obj = game.players.get(target_id)
        if target_obj:
            voter_names = [game.players.get(v_id).display_name for v_id in voter_ids if game.players.get(v_id)]
            count_message += f"- **{target_obj.display_name}** ({len(voter_ids)}): {', '.join(voter_names)}\n"

    living_player_ids = {p.id for p in game.players.values() if p.is_alive}
    voted_player_ids = set()
    for ids in game.lynch_votes.values():
        voted_player_ids.update(ids)
    not_voted_ids = living_player_ids - voted_player_ids
    if not_voted_ids:
        not_voted_names = [game.players[p_id].display_name for p_id in not_voted_ids if p_id in game.players]
        count_message += f"\n**Yet to vote ({len(not_voted_names)}):** {', '.join(not_voted_names)}"

    await channel.send(count_message)


async def tally_votes(game):
    """Determines outcome of the day's vote, lynches players with most votes, and checks Jester win."""
    living_player_ids = {p.id for p in game.players.values() if p.is_alive}
    voted_player_ids = set()
    for ids in game.lynch_votes.values():
        voted_player_ids.update(ids)
    not_voted_ids = living_player_ids - voted_player_ids
    inactivity_deaths = []
    phase_str = f"Day {game.game_settings.get('phase_number')}"

    max_missed = getattr(config, 'MAX_MISSED_VOTES', 2)
    for player_id in not_voted_ids:
        player_obj = game.players.get(player_id)
        if player_obj:
            player_obj.missed_votes += 1
            if player_obj.missed_votes >= max_missed:
                player_obj.kill(phase_str, "Inactivity")
                inactivity_deaths.append(player_obj)
                logger.info(f"Player {player_obj.display_name} has been killed for inactivity.")

    if inactivity_deaths:
        if hasattr(game, 'narration_manager') and game.narration_manager:
            game.narration_manager.add_event('inactivity_kill', victims=inactivity_deaths)
        for dead_player in inactivity_deaths:
            game._handle_promotions(dead_player)

    if not game.lynch_votes or not any(game.lynch_votes.values()):
        if hasattr(game, 'narration_manager') and game.narration_manager:
            game.narration_manager.add_event('no_lynch')
        return

    max_votes = len(max(game.lynch_votes.values(), key=len))
    lynched_player_ids = [t_id for t_id, v_ids in game.lynch_votes.items() if len(v_ids) == max_votes]
    lynched_players = [game.players.get(pid) for pid in lynched_player_ids if game.players.get(pid)]

    if not lynched_players:
        if hasattr(game, 'narration_manager') and game.narration_manager:
            game.narration_manager.add_event('no_lynch')
        return

    lynch_details = {}
    for victim in lynched_players:
        victim.kill(phase_str, "Lynched by the town")
        victim.death_info['voters'] = [
            p.display_name for p in [game.players.get(v_id) for v_id in game.lynch_votes.get(victim.id, [])] if p
        ]
        game._handle_promotions(victim)
        voters = [game.players.get(v_id) for v_id in game.lynch_votes.get(victim.id, [])]
        lynch_details[victim] = voters

    if hasattr(game, 'narration_manager') and game.narration_manager:
        game.narration_manager.add_event('lynch', victims=lynched_players, details=lynch_details)

    if len(lynched_players) == 1 and lynched_players[0].role and lynched_players[0].role.name == "Jester":
        if hasattr(game, 'narration_manager') and game.narration_manager:
            game.narration_manager.add_event('jester_win', victim=lynched_players[0])
        game.game_settings['winning_team'] = "Jester"
        return "Jester"

    return None

