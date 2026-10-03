# game/engine/voting.py
"""
Day Phase Voting and Lynch Resolution Subsystem.

Responsibilities:
1. Lynch Vote Processing (`process_lynch_vote`):
   - Protected by `async with game.vote_lock` to handle simultaneous concurrent votes cleanly.
   - Enforces that votes can only occur during the daytime phase.
   - Restricts voting to living players and prohibits targeting deceased players.
   - Automatically retracts prior votes when a player changes their vote to a new target.
   - Logs vote events in `game.vote_history` for Google Sheets and game summary exports.
2. Automated NPC Voting (`process_npc_votes`):
   - At the conclusion of the day, automatically casts votes for any living NPC bots that haven't voted.
   - Mafia bots prioritize voting for non-Mafia targets.
3. Vote Tallying & Execution (`tally_votes`):
   - Tracks missed votes: penalizes inactive living players and eliminates those who exceed max missed votes.
   - Counts total votes per candidate; resolves ties (both candidates eliminated in multi-lynch).
   - Checks if an eliminated player was a Jester, triggering an instant Jester win.
   - Clears vote tallies at the end of the day phase.
"""

import logging
import random
from datetime import datetime, timezone
import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def process_lynch_vote(game, interaction, voter_user, target_name):
    """
    Validates and registers a player's vote to lynch a target during the day phase.

    Concurrency:
    Guarded by `game.vote_lock` to prevent race conditions when multiple players vote simultaneously.

    Args:
        game (Game): The active game engine.
        interaction (discord.Interaction): Discord interaction object.
        voter_user (discord.User | discord.Member): The user submitting the vote.
        target_name (str): Display name of the player being voted for.

    Returns:
        str: User-facing confirmation or explanatory error message.
    """
    async with game.vote_lock:
        logger.info(f"Processing lynch vote from {voter_user.name} for target '{target_name}'")

        # 1. Reject votes outside the day phase
        if game.game_settings.get("current_phase") != "day":
            logger.warning(f"{voter_user.name} tried to vote outside of the day phase.")
            return "You can only vote during the day phase."

        # 2. Validate that the voter is a living participant in this match
        voter_obj = game.players.get(voter_user.id)
        if not voter_obj or not voter_obj.is_alive:
            logger.warning(f"{voter_user.name} tried to vote but is not a valid player or is dead.")
            return "You are not currently able to vote in this game."

        # 3. Validate that the target exists and is currently alive
        target_obj = game.get_player_by_name(target_name)
        if not target_obj:
            logger.warning(f"{voter_obj.display_name} tried to vote for non-existent player: {target_name}.")
            return f"Could not find a player named '{target_name}'."

        if not target_obj.is_alive:
            logger.warning(f"{voter_obj.display_name} tried to vote for dead player: {target_obj.display_name}.")
            return f"**{target_obj.display_name}** is already dead and cannot be voted for."

        # 4. Handle vote switching: remove prior vote from previous target
        if voter_obj.action_target is not None:
            previous_target_id = voter_obj.action_target
            if previous_target_id in game.lynch_votes and voter_obj.id in game.lynch_votes[previous_target_id]:
                game.lynch_votes[previous_target_id].remove(voter_obj.id)
                if not game.lynch_votes[previous_target_id]:
                    del game.lynch_votes[previous_target_id]

        # 5. Register the new vote in the tally
        voter_obj.action_target = target_obj.id
        game.lynch_votes.setdefault(target_obj.id, [])
        if voter_obj.id not in game.lynch_votes[target_obj.id]:
            game.lynch_votes[target_obj.id].append(voter_obj.id)

        # 6. Record vote entry in history for analytics and Google Sheets sync
        game.vote_history.append({
            "voter_id": voter_obj.id,
            "voter_name": voter_obj.display_name,
            "target_id": target_obj.id,
            "target_name": target_obj.display_name,
            "phase": f"Day {game.game_settings.get('phase_number')}",
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        })

        # 7. Announce the vote and update the public tally in the voting channel
        voting_channel = game.bot.get_channel(getattr(config, 'VOTING_CHANNEL_ID', 0))
        if voting_channel:
            await voting_channel.send(f"**{voter_obj.display_name}** has voted for **{target_obj.display_name}**.")
            await game.send_vote_count(voting_channel)
            return f"Your vote for **{target_obj.display_name}** has been recorded."
        else:
            return "Vote recorded, but could not find the voting channel to post an update."


async def send_vote_count(game, channel):
    """
    Constructs and broadcasts the live vote leaderboard to the specified voting channel.
    Also lists all living players who have yet to cast their vote today.
    """
    if not game.lynch_votes:
        await channel.send("No votes have been cast yet.")
        return

    count_message = "**Current Vote Tally:**\n"
    # Sort candidates by number of votes descending
    vote_data = sorted(game.lynch_votes.items(), key=lambda item: len(item[1]), reverse=True)
    for target_id, voter_ids in vote_data:
        target_obj = game.players.get(target_id)
        if target_obj:
            voter_names = [game.players.get(v_id).display_name for v_id in voter_ids if game.players.get(v_id)]
            count_message += f"- **{target_obj.display_name}** ({len(voter_ids)}): {', '.join(voter_names)}\n"

    # Identify living players who have not voted yet
    living_player_ids = {p.id for p in game.players.values() if p.is_alive}
    voted_player_ids = set()
    for ids in game.lynch_votes.values():
        voted_player_ids.update(ids)
    not_voted_ids = living_player_ids - voted_player_ids
    if not_voted_ids:
        not_voted_names = [game.players[p_id].display_name for p_id in not_voted_ids if p_id in game.players]
        count_message += f"\n**Yet to vote ({len(not_voted_names)}):** {', '.join(not_voted_names)}"

    await channel.send(count_message)


async def process_npc_votes(game):
    """
    Automatically casts lynch votes for any living virtual NPCs who haven't voted at day's end.

    NPC Strategy:
    - Chooses a random living target (excluding themselves).
    - If the NPC is Mafia, they prefer to target non-Mafia players.
    """
    living_npcs = [p for p in game.players.values() if p.is_npc and p.is_alive]
    if not living_npcs:
        return

    # Check which players have already voted
    voted_ids = set()
    for voter_list in game.lynch_votes.values():
        voted_ids.update(voter_list)

    voting_channel = game.bot.get_channel(getattr(config, 'VOTING_CHANNEL_ID', 0)) if game.bot else None

    for npc in living_npcs:
        if npc.id in voted_ids:
            continue

        eligible_targets = [p for p in game.players.values() if p.is_alive and p.id != npc.id]
        if not eligible_targets:
            continue

        # Mafia bots prioritize non-Mafia targets
        if getattr(npc.role, 'alignment', '') == "Mafia":
            non_mafia = [p for p in eligible_targets if getattr(p.role, 'alignment', '') != "Mafia"]
            target_obj = random.choice(non_mafia) if non_mafia else random.choice(eligible_targets)
        else:
            target_obj = random.choice(eligible_targets)

        npc.action_target = target_obj.id
        game.lynch_votes.setdefault(target_obj.id, [])
        if npc.id not in game.lynch_votes[target_obj.id]:
            game.lynch_votes[target_obj.id].append(npc.id)

        game.vote_history.append({
            "voter_id": npc.id,
            "voter_name": npc.display_name,
            "target_id": target_obj.id,
            "target_name": target_obj.display_name,
            "phase": f"Day {game.game_settings.get('phase_number')}",
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"NPC Vote: {npc.display_name} voted for {target_obj.display_name}")

        if voting_channel:
            try:
                await voting_channel.send(f"🤖 **{npc.display_name}** (NPC) has voted for **{target_obj.display_name}**.")
            except Exception as e:
                logger.debug(f"Failed to post NPC vote to channel: {e}")


async def tally_votes(game):
    """
    Determines the outcome of the day's vote, lynches the top vote-getters, and checks for Jester wins.

    Execution Flow:
    1. Automated NPC votes trigger for any lingering unvoted bots.
    2. Inactivity tracking: increments missed_votes counter for living non-voters.
       Eliminates players who hit `config.MAX_MISSED_VOTES`.
    3. Identifies candidate(s) with the maximum votes.
    4. Eliminates the condemned player(s) and records their death info and voter list.
    5. Checks if the lynched player was a Jester, awarding them an immediate victory.

    Returns:
        str | None: "Jester" if a Jester achieved their win condition; None otherwise.
    """
    # 1. Ensure all NPCs vote before counting
    await process_npc_votes(game)

    # 2. Check for inactivity penalties among living players who failed to vote
    living_player_ids = {p.id for p in game.players.values() if p.is_alive}
    voted_player_ids = set()
    for ids in game.lynch_votes.values():
        voted_player_ids.update(ids)
    not_voted_ids = living_player_ids - voted_player_ids
    inactivity_deaths = []
    phase_str = f"Day {game.game_settings.get('phase_number')}"

    max_missed = getattr(config, 'MAX_MISSED_VOTES', 2)
    if not isinstance(max_missed, int):
        max_missed = 2

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

    # 3. If no votes were cast at all, record a 'no_lynch' event and exit
    if not game.lynch_votes or not any(game.lynch_votes.values()):
        if hasattr(game, 'narration_manager') and game.narration_manager:
            game.narration_manager.add_event('no_lynch')
        return

    # 4. Find all candidates tied for the highest vote count
    max_votes = len(max(game.lynch_votes.values(), key=len))
    lynched_player_ids = [t_id for t_id, v_ids in game.lynch_votes.items() if len(v_ids) == max_votes]
    lynched_players = [game.players.get(pid) for pid in lynched_player_ids if game.players.get(pid)]

    if not lynched_players:
        if hasattr(game, 'narration_manager') and game.narration_manager:
            game.narration_manager.add_event('no_lynch')
        return

    # 5. Execute lynch on condemned players (handles multiple in case of a tie)
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

    # 6. Special Jester Win Condition: wins if eliminated via daytime lynch
    if len(lynched_players) == 1 and lynched_players[0].role and lynched_players[0].role.name == "Jester":
        if hasattr(game, 'narration_manager') and game.narration_manager:
            game.narration_manager.add_event('jester_win', victim=lynched_players[0])
        game.game_settings['winning_team'] = "Jester"
        return "Jester"

    return None
