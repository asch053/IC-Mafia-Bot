# cogs/communitycogs/reviewquirks.py
import logging
import discord
from community.review_system import QuirkReviewView
from community import quirk_logic

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def handle_review_quirks(self, interaction: discord.Interaction):
    """Loops through all pending quirks and provides approval buttons."""
    pending = quirk_logic.get_all_pending()
    if not pending:
        return await interaction.response.send_message("The queue is empty, cutie! 💅", ephemeral=True)

    await interaction.response.send_message("Fetching pending items...", ephemeral=True)
    for user_id_str, quirk_text in pending.items():
        user_id = int(user_id_str)
        current_approved = quirk_logic.get_user_quirk(user_id)

        embed = discord.Embed(title="Reviewing Quirk", color=discord.Color.orange())
        embed.add_field(name="Player", value=f"<@{user_id}>", inline=False)

        if current_approved:
            embed.add_field(name="Currently Active", value=f"*{current_approved}*", inline=True)
            embed.add_field(name="Proposed Change", value=f"**{quirk_text}**", inline=True)
        else:
            embed.add_field(name="New Quirk", value=f"\"{quirk_text}\"", inline=False)

        await interaction.channel.send(embed=embed, view=QuirkReviewView(user_id))

