# community/ui/rejectionselect.py
import discord
from discord import ui
import logging
from community import quirk_logic

logger = logging.getLogger('discord')

REJECTION_REASONS = [
    "Inappropriate content or language",
    "Harmful, mean, or targets others",
    "Breaking the fourth wall / Meta-gaming",
    "Does not fit the current game theme",
    "Too long or difficult for AI to parse"
]


class RejectionReasonSelect(ui.Select):
    """Dropdown for admins to select why they are rejecting a quirk."""
    def __init__(self, target_user_id: int):
        options = [discord.SelectOption(label=r, value=r) for r in REJECTION_REASONS]
        options.append(discord.SelectOption(label="Other/Minor Fix needed", value="Generic violation"))

        super().__init__(placeholder="Why are we rejecting this?", options=options)
        self.target_user_id = target_user_id

    async def callback(self, interaction: discord.Interaction):
        reason = self.values[0]
        quirk_text = quirk_logic.reject_quirk_logic(self.target_user_id)

        await interaction.response.edit_message(
            content=f"❌ **Rejected** quirk for <@{self.target_user_id}>\n**Reason:** {reason}",
            view=None, embed=None
        )

        try:
            user = await interaction.client.fetch_user(self.target_user_id)
            dm_text = (
                f"Hello! Your Mafia quirk submission has been **rejected** by an admin.\n\n"
                f"**Your submission:** \"{quirk_text}\"\n"
                f"**Reason:** {reason}\n\n"
                f"Feel free to submit a revised version with `/set_quirk`! ✍️"
            )
            await user.send(dm_text)
        except Exception:
            logger.warning(f"Could not DM rejection to user {self.target_user_id}")

