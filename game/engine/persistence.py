# game/engine/persistence.py
import os
import json
import logging
from collections import Counter
from datetime import datetime, timezone
import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def save_story_log(game, alignments, end_time):
    """
    Saves the full narrative history, player manifest, and chat log 
    to a Markdown file. 
    Compatible with both v0.5 (Static) and v0.6 (AI).
    """
    logger.info("Saving story log...")
    try:
        full_story = game.narration_manager.get_full_story_log()
        game_id = game.game_settings.get('game_id', 'unknown_game')
        output_dir = f"{config.data_save_path}/{game.game_settings.get('game_type', 'classic')}/{game.game_settings.get('game_id')}".title().replace('_', ' ')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"Created output directory: {output_dir}")
        else:
            logger.info(f"Output directory already exists: {output_dir}")

        filename = f"{output_dir}/game_{game_id}_story.md"
        logger.info(f"Story log will be saved to: {filename}")

        manifest_section = "## Cast of Characters\n\n| Player | Role | Status |\n| :--- | :--- | :--- |\n"
        for player_id, player in game.players.items():
            status = "Alive" if player.is_alive else f"Dead ({player.death_info.get('phase', 'Unknown')} - {player.death_info.get('how', 'Unknown')})"
            role_name = player.role.name if player.role else "Unknown"
            manifest_section += f"| **{player.display_name}** | {role_name} | {status} |\n"
        logger.info(f"Built player manifest section for story log.{output_dir}/{filename}")

        chat_section = ""
        logger.info("Building chat transcript section for story log.")
        if hasattr(game, 'chat_log') and game.chat_log:
            chat_section = "\n## Chat Transcript\n\nTimestamp| Channel | Phase | Player ID | Player Name | Message\n:--- | :--- | :--- | :--- | :---\n"
            for entry in game.chat_log:
                if isinstance(entry, dict):
                    timestamp = entry.get('timestamp_utc', '')
                    id = entry.get('user_id', '')
                    name = entry.get('username', 'Unknown')
                    channel = entry.get('channel_name', 'Unknown')
                    phase = entry.get('phase', 'N/A')
                    phase_number = entry.get('phase_number', 0)
                    msg = entry.get('content', '')
                    chat_section += f"**[{timestamp}], Channel: {channel}, Phase: {phase} - {phase_number}, Player ID: {id}, {name}:** {msg}\n\n"
                else:
                    chat_section += f"{str(entry)}\n\n"
            logger.info("Chat log included in story log.")
        else:
            chat_section = "\n## Chat Transcript\n\n_No chat log available._\n"
            logger.info("No chat log available to include in story log.")

        file_content = (
            f"# Game Story Log\n"
            f"**Game ID:** {game_id}\n"
            f"**Start date (UTC):** {game.game_settings.get('start_time').isoformat() if game.game_settings.get('start_time') else 'N/A'}\n"
            f"**End date (UTC):** {end_time.isoformat()}\n"
            f"Game Type: {game.game_settings.get('game_type', 'classic')}\n"
            f"Number of players: {len(game.players)}\n"
            f"Player counts: Town={alignments.get('Town', 0)}, Mafia={alignments.get('Mafia', 0)}, Neutral={alignments.get('Neutral', 0)}\n"
            f"Total days: {game.game_settings.get('phase_number')}\n"
            f"Phase hours: {game.game_settings.get('phase_hours')}\n"
            f"**Winning Team:** {game.game_settings.get('winning_team', 'Unknown')}\n\n"
            f"**Winning Players:** {sorted([p.display_name for p in game.players.values() if p.is_winner])}\n\n"
            f"{manifest_section}\n"
            f"{full_story}"
            f"{chat_section}"
        )
        logger.info(f"Final file content for story log prepared. Saving to {filename}")
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(file_content)
        logger.info(f"Story log successfully saved to {filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to save story log: {e}")
        return None


async def save_data_summary(game, game_data, final_summary):
    """Saves the game summary data to a JSON file in the appropriate stats directory."""
    logger.info("Saving game data summary...")
    try:
        game_id = game_data.get('game_id')
        if not game_id:
            logger.error("Cannot save summary, game_id is missing.")
            return

        game_type_dir = game.game_settings.get('game_type', 'classic').replace('_', ' ').title()
        base_dir = os.path.join(config.data_save_path, game_type_dir)
        game_log_dir = os.path.join(base_dir, game_id)
        os.makedirs(game_log_dir, exist_ok=True)
        file_path = os.path.join(game_log_dir, f"{game_id}_summary.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(final_summary, f, ensure_ascii=False, indent=4)
        logger.info(f"Game summary saved successfully to {file_path}")
    except Exception as e:
        logger.error(f"Failed to save game summary: {e}")


async def save_game_summary(game, winner):
    """Gathers all game data and saves it to a JSON file and story log."""
    logger.info(f"Saving game summary for game_id: {game.game_settings['game_id']}")
    end_time = datetime.now(timezone.utc)
    alignments = Counter(p.role.alignment for p in game.players.values() if p.role)

    phase_count = game.game_settings.get('phase_number', 0)
    last_phase = game.game_settings.get('current_phase', 'unknown').lower()
    if last_phase == 'day' or last_phase == 'pre-night':
        total_phases = (phase_count * 2)
    else:
        total_phases = (phase_count * 2) - 1

    game_data = {
        "game_id": game.game_settings.get('game_id'),
        "game_type": game.game_settings.get('game_type', 'classic'),
        "number_of_players": len(game.players),
        "player_counts": {
            "town": alignments.get("Town", 0),
            "mafia": alignments.get("Mafia", 0),
            "neutral": alignments.get("Neutral", 0)
        },
        "start_date_utc": game.game_settings.get('start_time').isoformat() if game.game_settings.get('start_time') else None,
        "end_date_utc": end_time.isoformat(),
        "total_days": game.game_settings.get('phase_number'),
        "phase_hours": game.game_settings.get('phase_hours'),
        "story_type": game.game_settings.get('story_type', 'Classic Mafia'),
        "mafia_ratio": game.game_settings.get('mafia_ratio'),
        "town_cop_req": game.game_settings.get('town_cop_req'),
        "town_doctor_req": game.game_settings.get('town_doctor_req'),
        "town_rb_req": game.game_settings.get('town_rb_req'),
        "mafia_rb_req": game.game_settings.get('mafia_rb_req'),
        "sk_player_count": game.game_settings.get('sk_player_count'),
        "gf_investigate": game.game_settings.get('gf_investigate'),
        "sk_investigate": game.game_settings.get('sk_investigate'),
        "gf_night_immune": game.game_settings.get('gf_night_immune', True),
        "sk_night_immune": game.game_settings.get('sk_night_immune', True),
        "br_skip_day": game.game_settings.get('br_skip_day', False),
        "total_phases": total_phases,
        "last_phase": last_phase,
        "winning_faction": winner,
        "winning_players": sorted([p.display_name for p in game.players.values() if p.is_winner])
    }

    player_data = []
    for player in sorted(game.players.values(), key=lambda p: p.display_name):
        player_data.append({
            "player_id": player.id,
            "player_name": player.display_name,
            "alignment": player.role.alignment if player.role else "Unknown",
            "role": player.role.name if player.role else "Unknown",
            "status": "Dead" if not player.is_alive else "Alive",
            "is_winner": player.is_winner,
            "death_phase": player.death_info.get('phase'),
            "death_cause": player.death_info.get('how'),
            "death_phase_number": player.death_info.get('phase_number'),
            "lynched_by_voters": player.death_info.get('voters')
        })

    lynch_data = game.vote_history
    chat_activity_logs = game.chat_log

    final_summary = {
        "game_summary": game_data,
        "player_data": player_data,
        "lynch_vote_history": lynch_data,
        "chat_activity_logs": chat_activity_logs
    }

    await save_data_summary(game, game_data, final_summary)
    await save_story_log(game, alignments, end_time)
    await export_game_stats(game)


async def export_game_stats(game):
    """Handles exporting game stats to Google Sheets or other platforms."""
    logger.info("Exporting game stats...")
    export_cog = game.bot.get_cog("ExportCog")
    channel = game.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
    if export_cog:
        await export_cog.run_export_logic(channel=channel, game_mode=game.game_settings.get('game_type', 'classic'))
        logger.info("Game stats exported.")
    else:
        logger.warning("Export Cog not found. Stats were not uploaded.")

