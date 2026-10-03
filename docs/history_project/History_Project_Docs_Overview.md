# History Project Documentation Subsystem Overview

The `/docs/history_project` directory contains the roadmap, engineering requirements, and AI prompt architecture for the **Mafia History Project**.

## 🧭 Navigation
- **Parent Hub**: [[Documentation_Hub_Overview]]
- **Connected Systems**: [[Mafia_History_Project_Overview]], [[Website_Portal_Overview]], [[Website_Data_Overview]]

---

## 📄 Documents in this Directory

| Document | Obsidian Link | Scope & Purpose |
| :--- | :--- | :--- |
| **Historic Project Plan** | [[HISTORIC_PROJECT_PLAN]] | Master engineering plan for Discourse scraping, token cleaning, phase detection, Gemini 3.1 Flash-Lite AI narrative summarization, and Google Sheets user mapping. |
| **High-Level Requirements** | [[docs/history_project/HIGH_LEVEL_REQUIREMENTS|History HLR]] | Requirements tables for data ingestion, BBCode token reduction, moderator detection, AI summarization with outcome inference, and batch archiving. |
| **Detailed Requirements** | [[docs/history_project/DETAILED_REQUIREMENTS|History DLR]] | Technical specifications for regex token sanitizers, LLM prompt engineering, retry backoff algorithms, schema definitions, and validation suites. |

---

## 🔗 Connected Overviews
- [[Documentation_Hub_Overview]]: Return to Docs Hub
- [[Mafia_History_Project_Overview]]: Codebase implementation in `Other Projects/Mafia History Project`
- [[Website_Portal_Overview]]: Web viewer consuming the generated `history_archive.json`
