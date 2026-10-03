# community/ui/reviewview.py
import discord
from discord import ui
import logging
from community import quirk_logic
from community.ui.rejectionselect import RejectionReasonSelect

logger = logging.getLogger('discord')


class QuirkReviewView(ui.View):
    """Approve/Reject buttons for individual quirks."""
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.target_user_id = user_id

    @ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        is_admin = interaction.user.guild_permissions.administrator if interaction.guild else False
        if not is_admin:
            return await interaction.response.send_message("Only admins! 💅", ephemeral=True)

        quirk = quirk_logic.approve_quirk_logic(self.target_user_id)
        await interaction.response.edit_message(
            content=f"✅ **Approved!**\nUser: <@{self.target_user_id}>\nQuirk: *{quirk}*",
            view=None, embed=None
        )

        try:
            user = await interaction.client.fetch_user(self.target_user_id)
            await user.send(f"Yay! Your quirk suggestion *\"{quirk}\"* was **approved**! 🎭")
        except Exception:
            pass

    @ui.button(label="Reject...", style=discord.ButtonStyle.red)
    async def reject_trigger(self, interaction: discord.Interaction, button: ui.Button):
        is_admin = interaction.user.guild_permissions.administrator if interaction.guild else False
        if not is_admin:
            return await interaction.response.send_message("Permission denied. ❌", ephemeral=True)

        new_view = ui.View()
        new_view.add_item(RejectionReasonSelect(self.target_user_id))
        await interaction.response.edit_message(content="Please select a rejection reason:", view=new_view)

