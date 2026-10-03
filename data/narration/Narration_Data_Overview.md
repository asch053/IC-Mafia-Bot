# Narration Data Assets Overview

The `/data/narration` directory contains story generation themes, pending player quirks, and active character concepts.

## 🧭 Navigation
- **Parent Subsystem**: [[Data_Assets_Overview]]
- **Related Modules**: [[Game_Narration_Overview]], [[Community_Quirks_Overview]]
- **Requirements Reference**: [[HIGH_LEVEL_REQUIREMENTS#Table-6-Narration--Storytelling-System]]

---

## 📄 File Index

| File | Format | Purpose |
| :--- | :--- | :--- |
| `themes.json` | JSON | Rich narrative settings across 9 distinct themes: Classic Mafia, Horror, Explicit Kinky NSFW (R18), Rom Com (SFW non-death), Office Restructuring (SFW non-death), High Fantasy, Cyberpunk, Comedy, and Lovecraftian Horror. Defines atmosphere, writing style, and Fog of War/custom rules for both classic and battle_royale modes. |
| `pending_quirks.json` | JSON | Moderation queue containing player quirks awaiting admin review. |
| `player_concepts.json` | JSON | Active repository of approved player roleplay quirks and character flavor. |

---

## 🔗 Connected Overviews
- [[Data_Assets_Overview]]: Return to Data Assets Index
- [[Game_Narration_Overview]]: AI narration engine injecting themes
- [[Community_Quirks_Overview]]: Quirk submission and approval operations
