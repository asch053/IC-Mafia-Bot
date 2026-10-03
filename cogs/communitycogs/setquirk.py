# cogs/communitycogs/setquirk.py
import logging
import discord
from community.review_system import QuirkSubmissionModal
from community import quirk_logic

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def handle_set_quirk(self, interaction: discord.Interaction):
    """Opens a modal, showing the user's current quirk if they have one."""
    target_id = self.admin_review_channel_id
    if target_id == 0:
        return await interaction.response.send_message("Review channel not configured! 🛠️", ephemeral=True)

    current = quirk_logic.get_user_quirk(interaction.user.id)
    await interaction.response.send_modal(QuirkSubmissionModal(target_id, current_quirk=current))

