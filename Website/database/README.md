# Mafia Game Database System

This directory houses the four modular source databases for the Imperial Conflict Mafia Bot and Archive Website.

## Modular Source Databases

1. **`historic_forum.json`**
   - Contains all **84 historical Forum era games** (Mafia 1 through Mafia 84).
   - Structured JSON holding game IDs, metadata, box scores (roster, outcomes, survivals, timeline, MVPs).
   - Points to markdown story files in `Website/stories/`.

2. **`historic_discourse.json`**
   - Contains all **35 Discourse era games** (Mafia 85 through modern Discourse games).
   - Holds structured outcomes, rosters, and points to markdown story files in `Website/stories/`.

3. **`discord_bot.json`**
   - Contains all automated **Discord Modern Bot games** produced by the bot.
   - Automatically updated whenever a game concludes on Discord.
   - Stores complete player rosters, vote histories, timelines, and points to markdown files in `Website/stories/`.

4. **`discord_manual.json`**
   - Dedicated file for any **manually run or community-hosted Discord games** outside the automated bot engine.
   - Edit this file directly in any text editor or JSON editor to add or adjust manual games.

---

## Story & Text Content Separation

Per design, actual long-form post text and narrative stories are **not** embedded inside these JSON database files. Instead, each match links to two dedicated Markdown files in `Website/stories/`:
- **`stories/{game_id}_summary.md`**: Synthesized tactical summary and match chronicle.
- **`stories/{game_id}_story.md`**: Verbatim original host briefing, phase announcements, scenes, and endgame debrief.

This allows any narrative or story text to be easily read, formatted, and edited directly in Markdown editors (such as VS Code or Obsidian).

---

## Build & Synchronization Tools

- **`Website/build_unified_leaderboard.py`**:
  - Compiles the four modular databases + markdown stories into the website's static delivery files: `Website/data/history_archive.json`, `leaderboard.json`, and `classic.json`.
  - Calculates Persuasion (P), Elusiveness (E), and Understanding (U) PEU skill scores across all 359+ players.

- **`scripts/sync_google_sheets.py`**:
  - Pushes all four modular databases (`Forum_Historic`, `Discourse_Historic`, `Discord_Bot`, `Discord_Manual`), the unified master `Games` tab, master `Players` tab, and master `Analytics` leaderboard tab to Google Sheets.
  - Can be run manually via CLI (`python scripts/sync_google_sheets.py`) or in Discord via `/exportstats`.
