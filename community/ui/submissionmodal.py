# community/ui/submissionmodal.py
import discord
from discord import ui
import logging
from community import quirk_logic

logger = logging.getLogger('discord')


class QuirkSubmissionModal(ui.Modal, title="Character Persona Suggestion"):
    """Modal for users to submit quirks, showing their existing one if applicable."""
    def __init__(self, admin_channel_id: int, current_quirk: str = ""):
        super().__init__()
        self.admin_channel_id = admin_channel_id
        self.quirk_input = ui.TextInput(
            label="How should the AI narrate you?",
            default=current_quirk,
            placeholder="Max 100 chars",
            max_length=100,
            required=True
        )
        self.add_item(self.quirk_input)

    async def on_submit(self, interaction: discord.Interaction):
        # 1. Save to pending queue
        quirk_logic.queue_pending_quirk(interaction.user.id, self.quirk_input.value)

        # 2. Alert admins
        admin_chan = interaction.client.get_channel(self.admin_channel_id)
        if admin_chan:
            old_quirk = quirk_logic.get_user_quirk(interaction.user.id)
            embed = discord.Embed(title="New Quirk Submitted", color=discord.Color.blue())
            embed.add_field(name="User", value=interaction.user.mention)

            if old_quirk:
                embed.add_field(name="Old Quirk", value=f"*{old_quirk}*", inline=False)
                embed.add_field(name="New Overwrite", value=f"**{self.quirk_input.value}**", inline=False)
            else:
                embed.add_field(name="Submission", value=self.quirk_input.value, inline=False)

            await admin_chan.send(embed=embed)

        await interaction.response.send_message("Submitted for review! I'll DM you once an admin decides. 😘", ephemeral=True)

