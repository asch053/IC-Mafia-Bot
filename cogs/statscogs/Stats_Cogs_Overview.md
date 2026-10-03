# Stats Cogs Subsystem Overview

The `/cogs/statscogs` directory powers the in-depth player statistics, game analytics, leaderboard rankings, and competitive Skill Score calculations.

## 🧭 Navigation
- **Parent Cog**: [[Cogs_Overview]]
- **Related Modules**: [[Export_Cogs_Overview]], [[Stats_Storage_Overview]], [[Website_Portal_Overview]]
- **Requirements Reference**: [[HIGH_LEVEL_REQUIREMENTS#Table-8-Statistics-Tracking--Analytics]], [[DETAILED_REQUIREMENTS#FR-STA-01-Player-Career-Profile]]

---

## 📄 File Index

| File | Command / Module | Description |
| :--- | :--- | :--- |
| `playerstats.py` | `/playerstats [player]` | Generates comprehensive player profile embed (wins, losses, win rates per faction, survival rate). |
| `gamestats.py` | `/gamestats [game_id]` | Displays detailed recap of a specific historical game (phases, lynches, kills, winner). |
| `leaderboard.py` | `/leaderboard` | Ranks server players across win counts, games played, and win percentages. |
| `hallofrecords.py` | `/hallofrecords` | Highlights historic achievements (e.g. longest survival, most night kills, perfect deduction). |
| `skillscore.py` | `/skillscore` | Displays competitive Skill Score rating for a given player based on weighted performance. |
| `skillscore_calc.py` | Rating Algorithm | Formula implementing skill score weighting win rate, survival, faction balance, and activity. |
| `calculators.py` | Analytics Engine | Statistical aggregation functions for win percentages, streaks, and kill/death ratios. |
| `loaders.py` | Data Loader | Reads and parses JSON game archives from `/stats` directory. |

---

## 🔗 Connected Overviews
- [[Cogs_Overview]]: Return to Cogs Index
- [[Stats_Storage_Overview]]: Directory storing raw game statistics and story archives
- [[Website_Portal_Overview]]: Web-based visual dashboard for these analytics
