<!-- Obsidian Navigation Header -->
> [!NOTE] Knowledge Graph Navigation
> - **Parent Documentation Hub**: [[Documentation_Hub_Overview]]
> - **Website Docs Hub**: [[Website_Docs_Overview]]
> - **Companion Document**: [[docs/website/HIGH_LEVEL_REQUIREMENTS|Website HLR]] | [[WEBSITE_PORTAL_PLAN]]
> - **Component Overviews**: [[Website_Portal_Overview]], [[Website_Data_Overview]], [[Mafia_History_Project_Overview]]
> - **Root Index**: [[Root_Project_Overview]]

# Imperial Conflict Mafia — Web Portal Detailed Requirements & Acceptance Criteria

## 1. Document Purpose
This document provides the detailed technical specification and acceptance criteria for the **Imperial Conflict Mafia Web Portal**. It defines the component-level directory structure, JavaScript module interfaces, data schemas, CSS design tokens, and automated test acceptance criteria.

---

## 2. Directory & Module Architecture

The portal is implemented as a client-side Single Page Application (SPA) structured as follows:

```
Website/
├── index.html                   # Shell container, view sections, modals
├── css/
│   ├── main.css                 # CSS variables, typography, global layout
│   ├── components.css           # Navigation, tables, stat-boxes, cards, loader
│   ├── codex.css                # Role cards, formula sliders, command cards
│   └── timeline.css             # Interactive phase timeline and story reader
├── js/
│   ├── app.js                   # Main entry point, router, view switcher
│   ├── api.js                   # Universal Dual-Mode Data Adapter
│   ├── charts.js                # Chart.js initialization and updates
│   ├── codex.js                 # Role card generator, formula calculator
│   ├── games.js                 # Modern game browser, story markdown reader
│   ├── history.js               # History Project era filter and thread reader
│   └── player.js                # Player dossier modal and badge evaluator
├── data/
│   ├── portal_data.json         # Static snapshot for leaderboards and KPIs
│   ├── games_archive.json       # Archive of modern bot games and stories
│   ├── role_definitions.json    # Synced from data/game_setup/role_definition.json
│   └── history_archive.json     # Curated historic forum/discourse archive
├── MafiaAPICode.js              # Google Apps Script Code.gs backend
└── archive/                     # Obsolete standalone files (classic.html, etc.)
```

---

## 3. Component & Module Specifications

### Module A: Core Infrastructure & Universal Data Adapter

#### A1. Universal Data Adapter (`js/api.js`)
* **Interface**:
  * `async function fetchPortalData(endpoint: string): Promise<any>`
  * `function isGoogleAppsScriptContext(): boolean`
* **Specification**:
  * Evaluates `typeof google !== 'undefined' && google.script && google.script.run`.
  * If in GAS context: wraps `google.script.run.withSuccessHandler(...).withFailureHandler(...)` in a native `Promise`.
  * If in standalone context: executes `fetch("./data/" + endpoint + ".json")` and parses response JSON.
* **Acceptance Criteria**:
  * `TEST-WEB-INF-01`: In a standard web browser without Google Apps Script, `fetchPortalData('portal_data')` resolves the contents of `./data/portal_data.json` without reference errors.
  * `TEST-WEB-INF-02`: Rejects gracefully with an identifiable error object if network fails or JSON syntax is invalid.

#### A2. SPA Router & View Switcher (`js/app.js`)
* **Interface**:
  * `function switchView(viewId: string): void`
  * `function getActiveView(): string`
* **Specification**:
  * Supported views: `'records'`, `'classic'`, `'battle_royale'`, `'codex'`, `'games'`, `'history'`, `'player'`.
  * Sets `.active` class on corresponding navigation button and removes `.hidden` class on the active `<div id="view-{viewId}">`.
  * Synchronizes browser URL hash (e.g. `window.location.hash = '#' + viewId`).
* **Acceptance Criteria**:
  * `TEST-WEB-INF-03`: Clicking any navigation tab displays the target view and hides all other view containers.
  * `TEST-WEB-INF-04`: On initial page load with `#codex` in URL, opens the Codex view directly.

---

### Module B: Analytics & Visualizations

#### B1. Leaderboard & Hall of Records Controller (`js/charts.js`)
* **Interface**:
  * `function renderRecordsTable(metricKey: string, playersData: Array<object>): void`
  * `function renderClassicDashboard(data: object): void`
  * `function renderBattleRoyaleDashboard(data: object): void`
* **Specification**:
  * Supports 18 metric configurations with custom sorting (descending for score, ascending for red shirt/death rates) and formatting (float, integer, percentage, inverse percentage).
  * Enforces minimum games threshold (default `> 5` games) to filter out 1-game anomalies.
* **Acceptance Criteria**:
  * `TEST-WEB-ANA-01`: Top 10 players correctly sorted by selected metric with rank medals (1st, 2nd, 3rd) on top 3.
  * `TEST-WEB-ANA-02`: Stacked faction trend line chart properly updates with Town (Blue), Mafia (Red), Neutral (Orange), Draw (Grey).

---

### Module C: Game Codex & Documentation

#### C1. Role Compendium Generator (`js/codex.js`)
* **Interface**:
  * `function renderRoleCompendium(rolesData: object, targetContainerId: string): void`
* **Specification**:
  * Fetches or receives `data/role_definitions.json`.
  * Generates responsive role cards displaying:
    * Role Name & Alignment (`Town`, `Mafia`, `Neutral`).
    * Badges: `Night Immune` (Shield icon), `Investigate Immune` (Eye-slash icon).
    * Abilities list (`kill`, `heal`, `investigate`, `block`).
    * Full Win Condition description.
* **Acceptance Criteria**:
  * `TEST-WEB-CDX-01`: Every role in `role_definitions.json` generates a structured HTML card with correct alignment styling.
  * `TEST-WEB-CDX-02`: Filter buttons (All, Town, Mafia, Neutral) instantly filter visible role cards without page reload.

#### C2. "Moneyball" Skill Score Visualizer (`js/codex.js`)
* **Interface**:
  * `function calculateSkillScore(P: number, E: number, U: number, wP: number, wE: number, wU: number): number`
  * `function updateFormulaDisplay(): void`
* **Specification**:
  * Interactively binds range sliders for Persuasion ($P$), Elusiveness ($E$), and Understanding ($U$) to display the composite formula output.
* **Acceptance Criteria**:
  * `TEST-WEB-CDX-03`: Moving sliders recomputes the score dynamically and updates DOM preview.

---

### Module D: Modern Game Explorer & Narrative Reader
 
#### D1. Game Catalog & Filter (`js/games.js`)
* **Interface**:
  * `function renderGameList(games: Array<object>): void`
  * `function filterGames(query: string, eraFilter: string, winnerFilter: string): void`
* **Specification**:
  * Renders a sortable table of all games across Forum, Discourse, and Discord eras.
  * Table columns: `Thread ID`, `Era`, `Game Title`, `Winner`, `Story & Actions`.
* **Acceptance Criteria**:
  * `TEST-WEB-GME-01`: Filtering by "Forum" and "Mafia" returns only matching games.
 
#### D2. AI Story & Narrative Reader (`js/games.js`)
* **Interface**:
  * `function openGameDetailModal(gameId: string): void`
  * `function renderStoryChapter(markdownText: string): string`
* **Specification**:
  * Parses markdown text using client-side `marked.js` and renders in a book-style reader with theme headers and italicized flavor quotes.
* **Acceptance Criteria**:
  * `TEST-WEB-GME-02`: Opening a game details modal displays the complete player box score and story chapters.

#### D3. Phase-by-Phase Play-by-Play & Timeline Engine (`js/games.js`)
* **Interface**:
  * `function renderPhasePlayByPlay(timeline: Array<object>, lynchVotes: Array<object>, phaseScenes: Array<object>): void`
* **Specification**:
  * Generates chronological visual cards for each phase:
    * `Preparation / Pre-game`: Roster setup, game rules.
    * `Day Phases`: Displays lynch targets, individual voting records (who voted for whom), and execution scene description.
    * `Night Phases`: Displays attacks, deaths, doctor saves, and roleblocks.
    * `Endgame`: Final surviving faction and win condition met.
* **Acceptance Criteria**:
  * `TEST-WEB-GME-03`: Selecting the "⚡ Play-by-Play" tab inside a game modal renders all recorded phases in chronological order with vote details and elimination causes.

---

### Module E: Player Dossier & Profile Modal

#### E1. Career Dossier Evaluator (`js/player.js`)
* **Interface**:
  * `function openPlayerDossier(playerName: string): void`
  * `function evaluateBadges(playerStats: object): Array<Badge>`
* **Specification**:
  * Collects player's stats across all games.
  * Computes role affinity: `% Townie`, `% Mafia`, `% PR (Cop/Doctor/RB)`.
  * Computes achievement badges:
    * `Untouchable`: Won without any lynch votes against them.
    * `Mastermind`: Won >= 3 games as Godfather.
    * `Red Shirt Survivor`: Survived >= 5 Night 1 phases.
* **Acceptance Criteria**:
  * `TEST-WEB-DOS-01`: Clicking a player row in any leaderboard opens the dossier modal populated with their career record.

---

### Module F: Mafia History Project Integration

#### F1. Historic Thread Indexer (`js/history.js`)
* **Interface**:
  * `function renderHistoryView(historyData: object): void`
  * `function filterHistoryByEra(eraName: string): void`
* **Specification**:
  * Loads `data/history_archive.json` containing 600+ forum and discourse threads.
  * Era filter options: `All`, `Forum (2012–2020)`, `Discourse`, `Discord`.
  * Search bar filters thread titles and original authors.
* **Acceptance Criteria**:
  * `TEST-WEB-HIS-01`: Selecting `Forum (2012–2020)` filters catalog to historic forum games with active links to original forum threads.
  * `TEST-WEB-HIS-02`: Displays AI game summary if available for that historic match.

---

## 4. Data Schemas (JSON Contracts)

### Contract 1: `portal_data.json`
```json
{
  "last_updated": "2026-10-03T14:00:00Z",
  "classic": {
    "gameStats": { "Total": 42, "Town": 22, "Mafia": 16, "Neutral": 2, "Draw": 2 },
    "trend": [
      { "date": "2025-11-01", "townPct": "50.0", "mafiaPct": "35.0", "neutralPct": "5.0", "drawPct": "10.0" }
    ],
    "leaderboard": [
      {
        "name": "PlayerOne",
        "skillScore": "4.25",
        "p_score": "1.45",
        "e_score": "1.30",
        "u_score": "1.50",
        "games": 18,
        "winRate": "66.7",
        "n1Deaths": 1,
        "d1Lynches": 0
      }
    ]
  },
  "battle_royale": {
    "totalGames": 15,
    "chart": { "labels": ["PlayerOne", "PlayerTwo", "Draw"], "values": [5, 4, 6] },
    "leaderboard": [
      { "name": "PlayerOne", "games": 12, "wins": 5, "winRate": "42", "survRate": "78", "n1Deaths": 0 }
    ]
  }
}
```

### Contract 2: `games_archive.json`
```json
[
  {
    "game_id": "game_20261001_01",
    "start_time": "2026-10-01T18:00:00Z",
    "game_type": "classic",
    "theme": "Lovecraftian Horror",
    "winning_faction": "Town",
    "total_phases": 6,
    "roster": [
      { "name": "Alice", "role": "Town Cop", "alignment": "Town", "survived": true, "is_winner": true },
      { "name": "Bob", "role": "Godfather", "alignment": "Mafia", "survived": false, "death_phase": "Day 3 (Lynch)", "is_winner": false }
    ],
    "story_markdown": "# The Shadow Over Innsmouth\n\n### Chapter 1: Night 1\nThe fog rolled into town...",
    "phase_events": [
      { "phase": "Night 1", "deaths": ["Charlie (Mob Kill)"], "saves": ["Alice"] },
      { "phase": "Day 1", "lynched": "David (4 votes)" }
    ]
  }
]
```

### Contract 3: `history_archive.json`
```json
[
  {
    "thread_id": "185_1234",
    "title": "Mafia 45: Return to Deep Space",
    "era": "Forum (2012–2020)",
    "start_date": "2014-04-12",
    "author": "OldSchoolMod",
    "posts_count": 482,
    "original_url": "https://imperialconflict.com/forum/viewtopic.php?id=1234",
    "winning_faction": "Mafia",
    "ai_summary": "A tense 14-player game set in deep space where the Mafia pulled off a decisive victory on Day 4 following a mislynch of the Town Cop.",
    "key_players": ["DarthVader", "StarLord", "Yoda"]
  }
]
```

---

## 5. Verification Plan

1. **Static Browser Test**: Open `Website/index.html` in Chrome, Firefox, and Edge directly via `file:///` and via local HTTP server. Verify 0 console errors and complete rendering of cached data.
2. **Responsive Layout Test**: Inspect mobile viewport (375px), tablet viewport (768px), and widescreen desktop (1600px).
3. **Data Adapter Mocking**: Verify that mocking `google.script.run` triggers the Apps Script branch, while unsetting it falls back cleanly to fetch.

---

## 🔗 Obsidian Knowledge Graph Links
- **Master Root Index**: [[Root_Project_Overview]]
- **Documentation Hub**: [[Documentation_Hub_Overview]]
- **Website Docs Hub**: [[Website_Docs_Overview]]
- **Website Development Plan**: [[WEBSITE_PORTAL_PLAN]]
- **Website High-Level Requirements**: [[docs/website/HIGH_LEVEL_REQUIREMENTS|Website HLR]]
- **Connected Overviews**:
  - [[Website_Portal_Overview]]: Web application files
  - [[Website_Data_Overview]]: Historical JSON archives
  - [[Mafia_History_Project_Overview]]: History pipeline extractor
