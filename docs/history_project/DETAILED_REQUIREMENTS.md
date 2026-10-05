<!-- Obsidian Navigation Header -->
> [!NOTE] Knowledge Graph Navigation
> - **Parent Documentation Hub**: [[Documentation_Hub_Overview]]
> - **History Project Docs Hub**: [[History_Project_Docs_Overview]]
> - **Companion Documents**: [[HISTORIC_PROJECT_PLAN]] | [[docs/history_project/HIGH_LEVEL_REQUIREMENTS|History HLR]]
> - **Component Overviews**: [[Mafia_History_Project_Overview]], [[Website_Portal_Overview]], [[Website_Data_Overview]]
> - **Root Index**: [[Root_Project_Overview]]

# Imperial Conflict Mafia — Historic Project Detailed Requirements & Unit Test Acceptance Criteria

## 1. Document Purpose
This document provides the detailed technical specifications and acceptance criteria for the **Imperial Conflict Mafia History Project** and its **AI Summarization Engine**. It defines input/output schemas, prompt architecture, algorithm contracts, and unit test specifications required to verify implementation.

---

## 2. Component Architecture & Script Specifications

```
Other Projects/Mafia History Project/
├── forumhistory_extractor.py        # Old forum scraper (PHPBB 82 pages)
├── discoursehistory_extractor.py    # Discourse forum API harvester
├── discordhistory_extractor.py      # Historical Discord channel harvester
├── historybot_config.py             # Channels, tokens, forum endpoints
├── classify_game_threads.py         # Thread classifier & boundary detector
├── user_mapper_exporter.py          # Identity mapping & Google Sheets sync
├── summarize_historic_games.py      # Gemini AI Narrative & Box Score Engine
├── export_history_archive.py        # Compiles final history_archive.json
├── logs/                            # Datestamped execution logs
└── output/                          # Harvester outputs and generated summaries
    ├── extracted_history.jsonl      # Raw forum posts
    ├── mafia_threads.json           # Catalog of 644 threads
    ├── username_mapping_template.csv# Cross-era player map
    └── summaries/                   # AI-generated game summary JSONs
```

---

## 3. Subsystem Specifications & Acceptance Criteria

### Subsystem A: Harvesters & Raw Data Ingestion

#### A1. Forum Thread & Post Harvester (`forumhistory_extractor.py`)
* **Signature**:
  * `def generate_pagination_urls(base_url: str, total_pages: int) -> list[str]`
  * `def extract_thread_metadata(page_soup: BeautifulSoup) -> list[dict]`
  * `def scrape_thread_posts(thread_id: str, total_pages: int) -> list[dict]`
* **Specification**:
  * Scrapes `https://imperialconflict.com/forum/viewforum.php?id=185` across 82 pages.
  * Honors 3-second request delay (`REQUEST_DELAY_SECONDS = 3`) to prevent IP bans.
  * Formats posts as JSON Lines with fields: `thread_id`, `post_id`, `author`, `timestamp`, `content_text`, `quotes`.
* **Acceptance Criteria**:
  * `TEST-HIS-EXT-01`: Successfully extracts topic title, thread ID, and reply count from forum table markup.
  * `TEST-HIS-EXT-02`: Strips HTML tags, trims whitespace, and cleanly extracts nested quote blocks (`[quote]...[/quote]`).
  * `TEST-HIS-EXT-03`: Automatically retries on HTTP 500/503 errors up to 3 times before logging error and moving to next page.

#### A2. Discourse & Discord Harvesters
* **File Paths**: `discoursehistory_extractor.py`, `discordhistory_extractor.py`
* **Specification**: Ingests Discourse topics via REST JSON endpoints (`https://discourse.imperialconflict.com/t/{topic_id}.json` and `post_stream.posts` traversal) and Discord history via bot message fetching (`limit=None`, `after=timestamp`).
* **Acceptance Criteria**:
  * `TEST-HIS-EXT-04`: Normalizes author names, timestamps (ISO 8601 UTC), and message content into identical JSONL schema.
  * `TEST-HIS-EXT-05`: Discourse harvester maps posts directly to their parent `topic_id` without polluting transcripts with global `/posts.json` data.

---

### Subsystem B: Thread Classification & Event Segmentation

#### B1. Game Thread Classifier (`classify_game_threads.py`)
* **Signature**: `def classify_thread(thread_meta: dict, sample_posts: list[dict]) -> str`
* **Specification**:
  * Classifies thread into one of four types:
    * `GAME_ACTIVE`: Actual playable Mafia match (contains moderator story, Day/Night phases, vote counts).
    * `SIGNUP`: Pre-game signup thread (e.g. title contains `"signups"`, `"sign-ups"`, `"sign ups"`).
    * `COMMENTARY`: Dead thread, post-game discussion, or banter.
    * `RULES_INFO`: Rule announcements or general setup guides.
* **Acceptance Criteria**:
  * `TEST-HIS-SEG-01`: Thread titled "Mafia 54 - USS Ziusudra" with > 50 posts classified as `GAME_ACTIVE`.
  * `TEST-HIS-SEG-02`: Thread titled "Mafia 55 signups" classified as `SIGNUP`.

#### B2. Phase & Event Boundary Segmenter (`classify_game_threads.py`)
* **Signature**: `def segment_game_phases(thread_posts: list[dict], mod_name: str) -> list[dict]`
* **Specification**:
  * Scans posts by game moderator to identify phase boundary markers:
    * Regex patterns: `r"(?i)(Day|Night)\s+(\d+)\s+(Begins|Ends|Resolution|Story)"`
    * Vote count markers: `r"(?i)(Vote Count|Current Tally|Final Tally)"`
    * Lynch markers: `r"(?i)(Lynched|Eliminated|Executed):\s*(\w+)"`
    * Endgame markers: `r"(?i)(Game Over|Mafia Wins|Town Wins|Roles Revealed)"`
* **Acceptance Criteria**:
  * `TEST-HIS-SEG-03`: Accurately extracts phase sequence (Day 1 -> Night 1 -> Day 2 -> Endgame).
  * `TEST-HIS-SEG-04`: Identifies lynch execution targets from moderator closing posts.

---

### Subsystem C: Cross-Era Identity Resolution (`user_mapper_exporter.py`)

#### C1. Username Harvester & Mapping Matrix
* **Signature**:
  * `def harvest_unique_authors(input_files: list[str]) -> dict[str, dict]`
  * `def export_mapping_template(author_data: dict, output_csv: str) -> None`
  * `def sync_to_google_sheets(csv_path: str, credentials_path: str) -> bool`
* **Specification**:
  * Reads `extracted_history.jsonl`, `discourse_history.jsonl`, `old_discord_history.jsonl`.
  * Normalizes author names (case-insensitive, trims punctuation).
  * Generates `username_mapping_template.csv` with columns: `canonical_name`, `discord_id`, `forum_handle`, `discourse_handle`, `discord_handle`, `total_posts`, `first_seen`, `last_seen`.
* **Acceptance Criteria**:
  * `TEST-HIS-MAP-01`: Generates CSV containing all unique authors sorted by post volume.
  * `TEST-HIS-MAP-02`: Existing manual mappings are preserved during update runs.

---

### Subsystem D: AI Summarization Engine (`summarize_historic_games.py`)

#### D1. Context Builder & Token Budget Manager
* **Signature**: `def build_game_prompt_context(game_thread: dict, phases: list[dict]) -> str`
* **Specification**:
  * Collects high-signal posts:
    1. Moderator opening theme post (setting the story).
    2. Moderator Day/Night resolution stories.
    3. Final vote tallies for each Day phase.
    4. Key player claims and prominent arguments (filtering out 1-line spam).
    5. Moderator endgame post (full role list and night actions).
  * Constrains context to < 100,000 tokens for Gemini 2.5 Flash / Pro.
* **Acceptance Criteria**:
  * `TEST-HIS-SUM-01`: Context contains all moderator phase posts and the endgame role list.
  * `TEST-HIS-SUM-02`: Strips forum BBCode formatting (`[b]`, `[i]`, `[img]`) to reduce token overhead.

#### D2. Gemini AI Game Chronicle Synthesizer
* **Signature**: `async def generate_game_chronicle(game_context: str, model_name: str = "gemini-2.5-flash") -> tuple[str, dict]`
* **Specification**:
  * System Prompt instructs Gemini to act as the official **Imperial Conflict Mafia Historian**.
  * Outputs two sections:
    1. **Narrative Game Chronicle (Markdown)**: Multi-chapter literary retelling of the game including opening theme, key deceptions, clutch saves, and final showdown.
    2. **Mechanical Box Score (JSON)**: Structured data adhering to `MechanicalBoxScore` schema.
* **Acceptance Criteria**:
  * `TEST-HIS-SUM-03`: Generates markdown story covering beginning, middle, and conclusion of the match.
  * `TEST-HIS-SUM-04`: Validates that JSON box score strictly matches required schema.

---

## 4. Data Contracts & JSON Schemas

### Contract 1: Raw Harvested Post (`extracted_history.jsonl`)
```json
{
  "thread_id": "203868",
  "thread_title": "Mafia 54 - USS Ziusudra",
  "post_id": "1452901",
  "author": "TheGameMaster",
  "is_mod": true,
  "timestamp": "2018-06-14T18:32:00Z",
  "content_text": "Day 1 has concluded. With 7 votes, StarLord has been lynched. He was Plain Townie.",
  "quotes": []
}
```

### Contract 2: AI Summarized Game Output (`summaries/game_<ID>.json`)
```json
{
  "game_id": "forum_203868",
  "title": "Mafia 54: USS Ziusudra",
  "era": "Forum (2012–2020)",
  "moderator": "TheGameMaster",
  "thread_url": "https://imperialconflict.com/forum/viewtopic.php?id=203868",
  "dates": { "start": "2018-06-10", "end": "2018-06-22" },
  "winning_faction": "Mafia",
  "mvp": {
    "player": "DarthVader",
    "role": "Godfather",
    "rationale": "Successfully framed the Town Cop on Day 3 and led the Mafia to a flawless victory without losing a single member."
  },
  "narrative_chronicle": "# Mafia 54: The Voyage of USS Ziusudra\n\n### Chapter 1: The Gathering Stars\nIn the cold silence of deep space...",
  "story_as_written": "## 📜 Opening Briefing & Lore\n*Original opening by Moderator TheGameMaster*\n\nWelcome to Mafia 54...\n\n---\n\n## ⚔️ Phase Announcements & Night Stories\n### Night 1 Narrative Scene\n...",
  "box_score": {
    "total_players": 14,
    "total_phases": 8,
    "roster": [
      { "player_name": "DarthVader", "role": "Godfather", "alignment": "Mafia", "survived": true },
      { "player_name": "Yoda", "role": "Town Cop", "alignment": "Town", "death_phase": "Day 3 (Lynch)", "survived": false }
    ],
    "timeline": [
      { "phase": "Day 1", "event": "Lynch", "target": "StarLord", "votes": 7, "revealed_role": "Plain Townie" },
      { "phase": "Night 1", "event": "Kill", "target": "HanSolo", "killer": "Mafia" }
    ]
  }
}
```

#### D3. Dual-Mode Story & Summary Architecture
* **Specification**:
  * Every game record retains two distinct narrative texts:
    1. **`narrative_chronicle`**: AI-synthesized multi-chapter literary summary chronicle (retelling key events, tactical pivots, and resolution).
    2. **`story_as_written`**: Verbatim original moderator story posts harvested from the match archive (Opening lore & theme, phase announcements, night kills, vote counts, and endgame role reveal epilogue).
  * Web portal modal displays both in dedicated tabs: **📋 Game Summary** and **📖 Stories as Written**.


### Contract 3: Compiled Web Portal Archive (`Website/data/history_archive.json`)
```json
{
  "total_games": 85,
  "eras": ["Forum (2012–2020)", "Discourse Era", "Discord Era"],
  "games": [
    {
      "game_id": "forum_203868",
      "title": "Mafia 54: USS Ziusudra",
      "era": "Forum (2012–2020)",
      "moderator": "TheGameMaster",
      "start_date": "2018-06-10",
      "winning_faction": "Mafia",
      "player_count": 14,
      "mvp": "DarthVader (Godfather)",
      "summary": "A deep space sci-fi thriller where the Mafia claimed a flawless victory after framing the Town Cop.",
      "original_url": "https://imperialconflict.com/forum/viewtopic.php?id=203868"
    }
  ]
}
```

---

## 5. Automated Unit Test Acceptance Criteria

| Test ID | Target Component | Description | Expected Result |
| :--- | :--- | :--- | :--- |
| `TEST-HIS-01` | `forumhistory_extractor.py` | Parse sample forum thread HTML | Correctly extracts thread title, ID, author, and all reply posts. |
| `TEST-HIS-02` | `classify_game_threads.py` | Classify game vs signup threads | Correctly tags matches as `GAME_ACTIVE` and signups as `SIGNUP`. |
| `TEST-HIS-03` | `classify_game_threads.py` | Detect phase transitions | Identifies Day/Night transitions from sample moderator posts. |
| `TEST-HIS-04` | `user_mapper_exporter.py` | CSV generation & normalization | Deduplicates author handles and writes valid CSV template. |
| `TEST-HIS-05` | `summarize_historic_games.py` | Context builder token limits | Prunes non-essential banter while preserving mod stories and endgame reveals (< 100k tokens). |
| `TEST-HIS-06` | `summarize_historic_games.py` | Gemini Prompt Generation | Builds structured prompt with system instructions, phase events, and required JSON schema. |
| `TEST-HIS-07` | `summarize_historic_games.py` | JSON Box Score Validation | Validates that mock LLM output conforms to `MechanicalBoxScore` contract. |
| `TEST-HIS-08` | `export_history_archive.py` | Web Portal JSON compiler | Compiles individual game summaries into unified `history_archive.json`. |

---

## 🔗 Obsidian Knowledge Graph Links
- **Master Root Index**: [[Root_Project_Overview]]
- **Documentation Hub**: [[Documentation_Hub_Overview]]
- **History Project Docs Hub**: [[History_Project_Docs_Overview]]
- **History Project Plan**: [[HISTORIC_PROJECT_PLAN]]
- **High-Level Requirements**: [[docs/history_project/HIGH_LEVEL_REQUIREMENTS|History HLR]]
- **Connected Overviews**:
  - [[Mafia_History_Project_Overview]]: Pipeline code and AI prompt specifications
  - [[Website_Portal_Overview]]: Web portal integration
  - [[Website_Data_Overview]]: Output JSON schemas
