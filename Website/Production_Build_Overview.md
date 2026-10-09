# Production Build & Automated Game Updates Overview

This document summarizes the production setup architecture for the **IC Mafia Bot** and its **Website Analytics Portal**, detailing how games played on Discord automatically update website stories, databases, and leaderboards.

For the comprehensive, step-by-step installation instructions for Oracle Cloud VM, Caddy/Nginx web server, systemd services, and firewall rules, see:
👉 **[PRODUCTION_SETUP_GUIDE.md](file:///f:/IC%20Mafia%20Bot/Website/PRODUCTION_SETUP_GUIDE.md)**

---

## ⚡ Real-Time Game-to-Website Flow

When a match ends in Discord, the bot's persistence pipeline executes automatically:

1. **`persistence.py:save_game_summary(game, winner)`**:
   - Compiles final statistics and saves local match logs.
2. **`persistence.py:update_modular_database(game, game_data, final_summary, winner)`**:
   - Generates and writes markdown summaries and narratives to:
     - `Website/stories/<game_id>_summary.md`
     - `Website/stories/<game_id>_story.md`
   - Appends the match box score (timeline, roster, vote history, survival records) into `Website/database/discord_bot.json`.
   - Executes `Website.build_unified_leaderboard.build_unified_stats(False)` asynchronously in a thread.
3. **Artifact Generation**:
   - Recalculates career metrics across all 4 eras (Classic Forum, Discourse, Discord Manual, Discord Bot).
   - Generates fresh static JSON data:
     - `Website/data/history_archive.json`
     - `Website/data/leaderboard.json`
     - `Website/data/classic.json`
     - `Website/data/battleroyale.json`
4. **Instant Web Delivery**:
   - Because the production web server (Caddy / Nginx) hosts the `Website/` directory on the same machine, the files are immediately available on the web without any deployment lag.
   - Cache-control headers (`no-cache, must-revalidate`) ensure client browsers fetch the newly compiled JSON on page load.
5. **Multi-Era Sync**:
   - `export_game_stats(game)` synchronizes match details to Google Sheets and refreshes Discord champion roles.

---

## 🚀 Quick Setup Checklist

| Component | Target Location / Command | Notes |
| :--- | :--- | :--- |
| **Hosting Environment** | Oracle Cloud Free Tier VM (Ubuntu 22.04/24.04 LTS) | Always Free Ampere A1 (up to 4 OCPU, 24GB RAM) or AMD micro instance |
| **Firewall Ports** | Ports `80` (HTTP) and `443` (HTTPS) | Ingress rules opened in Oracle VCN Security List & Ubuntu `iptables` |
| **Web Server** | Caddy or Nginx | Serves `/home/ubuntu/ic-mafia-bot/Website` with dynamic JSON cache-busting |
| **Bot Process** | Systemd service: `ic-mafia-bot.service` | Keeps bot running 24/7 with auto-restart on reboot or failure |
| **Data Build** | `python3 Website/build_unified_leaderboard.py` | Initial build command and manual re-compilation trigger |
| **Google Sheets Sync** | `python3 scripts/sync_google_sheets.py` | Syncs database tabs and rules setup to Google Sheets |

For detailed config snippets (Caddyfile, Nginx config, systemd unit file, iptables commands), refer to **[PRODUCTION_SETUP_GUIDE.md](file:///f:/IC%20Mafia%20Bot/Website/PRODUCTION_SETUP_GUIDE.md)**.
