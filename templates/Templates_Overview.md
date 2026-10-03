# Templates & Dev Tools Overview

The `/templates` directory contains template configuration files for deployment and local developer tooling for analyzing test coverage.

## 🧭 Navigation
- **Parent Hub**: [[Root_Project_Overview]]
- **Related Modules**: [[Bot_Setup_Overview]], [[Tests_Overview]]
- **Requirements Reference**: [[HIGH_LEVEL_REQUIREMENTS]]

---

## 📄 File Index

| File | Purpose | Notes |
| :--- | :--- | :--- |
| `.env.template` | Sample environment variable file documenting required keys (`BOT_TOKEN`, `CHANNEL_ID`, Google AI keys). | Copy to `.env` in root. |
| `config_template.py` | Template Python configuration file for server-specific role IDs and channel parameters. | Copy to `config.py` in root. |
| `analyze_coverage.py` | Developer utility that parses `pytest --cov` outputs and generates test coverage summaries. | Used during QA reviews. |
| `.gitignore copy` | Backup reference gitignore file for repository initialization. | Reference file. |

---

## 🔗 Connected Overviews
- [[Root_Project_Overview]]: Return to Master Hub
- [[Bot_Setup_Overview]]: Review how configuration variables are loaded
- [[Tests_Overview]]: Run test coverage scripts
