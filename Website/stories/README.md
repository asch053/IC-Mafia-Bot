# Mafia Stories & Match Chronicles Directory

This directory stores all written narratives, match summaries, and original post chronologies as standalone Markdown (`.md`) files.

## File Naming Convention

For every game with ID `{game_id}` (e.g. `203868`, `8118`, `20250815-220000`, `manual-example-01`):

1. **`{game_id}_summary.md`**:
   - The strategic match overview, tactical breakdown, and executive summary.
   - Displayed under **Tab 1: 📋 Summary** in the website's game modal.

2. **`{game_id}_story.md`**:
   - The verbatim original host briefings, lore, phase transition scenes, vote tally announcements, and endgame epilogues.
   - Displayed under **Tab 2: 📖 Story** in the website's game modal.

## Ineligible Games
Matches that were never started, remained in sign-ups, lacked player registration, or were non-game discussions (petitions, rule ideas, etc.) are excluded from the competitive leaderboards and archived in:
- `Website/stories/ineligible games/`

Their full narratives and chronicles are preserved in this sub-folder for historical reference without skewing match analytics.

## Editing Stories

You can open and edit any `.md` file in this directory using any Markdown editor (VS Code, Obsidian, Typora, Notepad, etc.).

After making edits, run:
```bash
python Website/build_unified_leaderboard.py
```
This automatically updates `Website/data/history_archive.json` so the website displays your updated text immediately!
