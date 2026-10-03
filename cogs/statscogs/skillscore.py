# cogs/statscogs/skillscore.py
import logging
import discord
from cogs.statscogs.skillscore_calc import calculate_skill_scores

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def handle_skill_score(self, interaction: discord.Interaction, member: discord.User = None):
    await interaction.response.defer(ephemeral=True)
    target = member or interaction.user

    games_by_mode = self._load_and_group_games()
    if not games_by_mode:
        await interaction.followup.send("No game logs found to analyze.", ephemeral=True)
        return

    classic_games = games_by_mode.get('classic', [])
    if not classic_games:
        await interaction.followup.send("No 'Classic' mode games found.", ephemeral=True)
        return

    try:
        data = calculate_skill_scores(target.id, classic_games)

        embed = discord.Embed(title=f"Skill Score: {target.display_name}", color=discord.Color.gold())
        if hasattr(target, 'display_avatar') and hasattr(target.display_avatar, 'url'):
            embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🏆 Score", value=f"**{data['final_score']:.2f} / 5.0**", inline=False)
        embed.add_field(name="🧠 Persuasion", value=f"{data['persuasion_norm']:.2f}", inline=True)
        embed.add_field(name="🕶️ Elusiveness", value=f"{data['elusiveness_norm']:.2f}", inline=True)
        embed.add_field(name="⚖️ Understanding", value=f"{data['understanding_norm']:.2f}", inline=True)
        embed.set_footer(text=f"Based on {data['total_games_played']} Classic games.")

        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        logger.error(f"Skillscore error: {e}", exc_info=True)
        await interaction.followup.send(f"An error occurred while calculating skill score: {e}", ephemeral=True)

