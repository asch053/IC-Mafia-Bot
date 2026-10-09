# Game Narration Subsystem Directory Overview

The `/game/narration` directory is dedicated to the narration and storytelling subsystem, housing modular story templates, prompt engineers, and AI narrative connectors.

## 🧭 Navigation
- **Parent Subsystem**: [[Game_System_Overview]]
- **Related Modules**: [[Narration_Data_Overview]], [[Logs_Directory_Overview]]
- **Requirements Reference**: [[HIGH_LEVEL_REQUIREMENTS#Table-6-Narration--Storytelling-System]], [[DETAILED_REQUIREMENTS#FR-NAR-01-Dual-Mode-Narration-Architecture]]

---

## 📖 Subsystem Structure & Architecture

The narration system supports **Dual-Mode Narration**:
1. **Generative AI Narration (`game/narration_ai.py`)**: Uses Google Gemini API to craft narrative stories incorporating player names, roles, quirks, chosen themes (Classic, Horror, Rom Com, Office Restructuring, etc.), and recent phase events.
2. **Deterministic Static Narration (`game/narration_static.py`)**: Built-in template fallback guaranteeing continuous storytelling even during API timeouts or offline play.
3. **Factual Mechanical Summary**: Prepended to the story output at phase transitions to guarantee critical eliminations and saves are communicated unambiguously regardless of LLM creative flair.

### 🛡️ Roleblock Visibility & Fog-of-War Invariants
To preserve player role secrecy and game balance:
- **Action-Focused Descriptions**: Blocked actions (e.g. thwarted murder, intercepted protection, blocked interference) are narrated without naming living players or revealing their roles.
- **Investigation Blocks**: Strictly suppressed from public stories and mechanical summaries (investigators receive private DM results only).
- **Conditional Heals**: Blocked heals are only narrated if an unblocked kill targeted that patient tonight. If the patient was not attacked, zero narration is produced.
- **Idle / Plain Townie Blocks**: Blocked players with no submitted night action produce zero public events.

```mermaid
flowchart TD
    Boundary["Phase Transition Event (Lynch or Night Kill)"] --> Dispatcher["game/narration.py"]
    
    Dispatcher --> Filter["Event Filter (Suppress Private/Idle Events)"]
    Filter --> Mech["Mechanical Summary Generator"]
    Filter --> Check{"AI Enabled & Key Present?"}
    Check -->|Yes| Gemini["game/narration_ai.py<br>(Gemini 3.1 Flash-Lite)"]
    Check -->|No / Fallback| Static["game/narration_static.py<br>(Pre-defined Templates)"]
    
    Gemini -->|Success| Publish["Combine Summary + Story<br>& Post to Guild Channel"]
    Gemini -->|Rate Limit / Error| Static
    Static --> Publish
    
    Gemini --> Archive["logs/prompts_archive.json"]
```

---

## 🔗 Connected Overviews
- [[Game_System_Overview]]: Return to Game System Index
- [[Narration_Data_Overview]]: Narrative themes and flavor profiles in `/data/narration`
- [[Logs_Directory_Overview]]: Archives of AI prompt requests and outputs
