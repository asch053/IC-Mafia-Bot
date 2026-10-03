# cogs/communitycogs/displayquirks.py
import logging
import discord
from community import quirk_logic

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def handle_display_quirks(self, interaction: discord.Interaction):
    """Displays all currently approved quirks in a batched list."""
    approved = quirk_logic.get_all_approved()
    if not approved:
        return await interaction.response.send_message("No approved quirks found! 🏜️", ephemeral=True)

    await interaction.response.send_message("Generating quirks list...", ephemeral=True)
    embed = discord.Embed(title="Approved Player Quirks", color=discord.Color.green())
    content = ""
    for uid, quirk in approved.items():
        line = f"<@{uid}>: {quirk}\n"
        if len(content) + len(line) > 3800:
            embed.description = content
            await interaction.followup.send(embed=embed, ephemeral=True)
            content, embed = line, discord.Embed(title="Approved Player Quirks (Cont.)", color=discord.Color.green())
        else:
            content += line
    if content:
        embed.description = content
        await interaction.followup.send(embed=embed, ephemeral=True)

