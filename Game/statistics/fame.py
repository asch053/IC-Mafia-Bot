# game/statistics/fame.py

import discord
import logging
import json
import os
import re
from discord.ext import commands
from discord import app_commands
from collections import defaultdict
from Utils.utilities import filter_games_by_time, load_data

logger = logging.getLogger('discord')

class FameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.roles_file = "./Data/discord_roles.json"

    async def update_champion_roles(self, guild: discord.Guild, mode: str = "classic") -> discord.Embed:
        """Calculates champions for a specific mode, updates roles, and returns an Embed."""
        logger.info(f"🏆 Running Champion Role Updates for {mode.upper()}...")
        
        all_roles = load_data(self.roles_file) or {}
        role_map = all_roles.get(mode, {})
        
        if not role_map:
            return discord.Embed(title="❌ Error", description=f"No roles configured for `{mode}` in discord_roles.json.", color=discord.Color.red())

        stats_cog = self.bot.get_cog("StatsCog")
        if not stats_cog:
            return discord.Embed(title="❌ Error", description="StatsCog is not loaded.", color=discord.Color.red())

        games_by_mode = stats_cog._load_and_group_games()
        raw_games = games_by_mode.get(mode, [])
        recent_games = filter_games_by_time(raw_games, days=182)
        
        if not recent_games:
            return discord.Embed(title="⚠️ Not Enough Data", description=f"No {mode} games played in the last 6 months.", color=discord.Color.orange())

        # --- UPDATED: Added total_game_phases to the tracker ---
        all_players = defaultdict(lambda: {"name": "Unknown", "games_played": 0, "deaths": 0, "survived": 0, "wins": 0, "phases_lived": 0, "total_game_phases": 0, "id": None})
        
        for game in recent_games:
            # Safely grab the total length of the game (Default to 1 to avoid division by zero)
            game_total_phases = max(1, int(game.get('game_summary', {}).get('total_phases', 1)))

            for p in game.get('player_data', []):
                try:
                    pid_int = int(p.get('player_id', 0))
                except (ValueError, TypeError):
                    continue
                    
                if pid_int <= 0:
                    continue

                # --- NEW: VOID INACTIVITY GAMES ---
                # Grab the cause of death and make it lowercase to avoid capitalization typos
                death_cause = str(p.get('death_cause', '')).lower()
                if death_cause == "inactivity":
                    continue  # Instantly skips them! Pretend they didn't play this game.
                
                pid = str(pid_int)
                all_players[pid]["id"] = pid_int
                all_players[pid]["name"] = p.get('player_name', all_players[pid]["name"])
                all_players[pid]["games_played"] += 1
                all_players[pid]["total_game_phases"] += game_total_phases
                
                if p.get('status') == 'Dead':
                    all_players[pid]["deaths"] += 1
                else:
                    all_players[pid]["survived"] += 1
                    
                if p.get('is_winner', False):
                    all_players[pid]["wins"] += 1

                phases = p.get('phases_lived')
                if phases is None:
                    dp = str(p.get('death_phase', ''))
                    match = re.search(r'\d+', dp)
                    phases = int(match.group()) if match else 0
                    
                    if p.get('status') != 'Dead':
                        phases = game_total_phases

                all_players[pid]["phases_lived"] += int(phases)

        eligible_players = {pid: data for pid, data in all_players.items() if data["games_played"] > 5}
        
        if not eligible_players:
            return discord.Embed(title="⚠️ No Eligible Players", description="Nobody has >5 games in the last 6 months.", color=discord.Color.orange())
            
        for pid, data in eligible_players.items():
            data["survival_rate"] = data["survived"] / data["games_played"]
            data["avg_phases_lived"] = data["phases_lived"] / data["games_played"]
            
            # --- NEW: Calculate the critical Phase Survival Percentage ---
            data["phase_survival_pct"] = data["phases_lived"] / data["total_game_phases"]
            logger.critical(f"Player ID {pid} ({data['name']}) - Phase Survival %: {data['phase_survival_pct']:.2%} ({data['phases_lived']} phases lived / {data['total_game_phases']} total phases)")

            if mode == "classic":
                skill_data = stats_cog._calculate_skill_scores(data["id"], recent_games)
                data["skill_score"] = skill_data["final_score"]

        # --- UPDATED: Added a "lowest" flag so we can hunt for the absolute WORST score ---
        def get_winners(metric_key, lowest=False):
            if lowest:
                target_val = min(p[metric_key] for p in eligible_players.values())
            else:
                target_val = max(p[metric_key] for p in eligible_players.values())
                
            winner_ids = [p["id"] for p in eligible_players.values() if p[metric_key] == target_val]
            return winner_ids, target_val

        # Route the winning criteria based on the mode
        if mode == "classic":
            winners = {
                "top_skill": get_winners("skill_score"),
                "top_survivor": get_winners("survival_rate"),
                # Look for the MINIMUM phase survival percentage!
                "red_shirt": get_winners("phase_survival_pct", lowest=True)
            }
        else:
            winners = {
                "top_wins": get_winners("wins"),
                "top_survivor": get_winners("avg_phases_lived"), 
                # Look for the MINIMUM phase survival percentage!
                "red_shirt": get_winners("phase_survival_pct", lowest=True)
            }

        results_log = []

        for category, role_id in role_map.items():
            role = guild.get_role(role_id)
            if not role: 
                logger.warning(f"Role ID {role_id} for {category} not found in server.")
                continue
            
            winner_data = winners.get(category)
            winner_ids = winner_data[0] if winner_data else []
            
            for member in role.members:
                if member.id not in winner_ids:
                    await member.remove_roles(role)
                    results_log.append(f"Removed {role.mention} from **{member.display_name}**")

            for w_id in winner_ids:
                winner_member = guild.get_member(w_id)
                if winner_member and role not in winner_member.roles:
                    await winner_member.add_roles(role)
                    results_log.append(f"👑 Awarded {role.mention} to **{winner_member.display_name}**!")

        mode_title = "Classic" if mode == "classic" else "Battle Royale"
        embed = discord.Embed(
            title=f"🏆 6-Month Champions ({mode_title})",
            description=f"Here are the reigning mathematically-calculated champions for the current {mode_title} season:",
            color=discord.Color.gold() if mode == "classic" else discord.Color.red()
        )

        survivor_label = "🛡️ Ultimate Survivor (Highest Survival %)" if mode == "classic" else "🛡️ Ultimate Survivor (Highest Avg Phases Lived)"
        
        cat_labels = {
            "top_skill": "👑 MVP (Highest Skill Score)",
            "top_wins": "⚔️ Top Gladiator (Most Wins)",
            "top_survivor": survivor_label,
            # Updated the label to reflect the new math!
            "red_shirt": "👕 The Red Shirt (Lowest Phase Survival %)"
        }
        
        for category, (winner_ids, target_val) in winners.items():
            names = []
            for w_id in winner_ids:
                member = guild.get_member(w_id)
                names.append(f"**{member.display_name}**" if member else f"<@{w_id}>")
            
            if category == "top_skill":
                stat_str = f"{target_val:.2f}"
            elif category == "top_wins":
                stat_str = f"{int(target_val)}"
            elif category == "top_survivor" and mode == "classic":
                stat_str = f"{target_val * 100:.1f}%"
            elif category == "top_survivor" and mode == "battle_royale":
                stat_str = f"{target_val:.1f} phases"
            elif category == "red_shirt":
                # Formats like: (Score: 12.5%)
                stat_str = f"{target_val * 100:.1f}%"
            else:
                stat_str = str(target_val)

            display_names = ", ".join(names) if names else "Nobody qualified!"
            
            if names:
                display_names += f"  *(Score: {stat_str})*"

            embed.add_field(name=f"## {cat_labels.get(category, category)}", value=display_names, inline=False)

        log_text = "\n".join(results_log) if results_log else "*No role changes necessary; the reigning champions held their titles!*"
        embed.add_field(name="## System Log", value=log_text, inline=False)

        return embed

    @app_commands.command(name="crown_champions", description="[Admin] Manually recalculate and award 6-month Champion Roles.")
    @app_commands.describe(mode="Which game mode to award roles for?")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Classic", value="classic"),
        app_commands.Choice(name="Battle Royale", value="battle_royale")
    ])
    @app_commands.default_permissions(administrator=True)
    async def crown_champions_cmd(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=False)
        embed = await self.update_champion_roles(interaction.guild, mode.value)
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(FameCog(bot))