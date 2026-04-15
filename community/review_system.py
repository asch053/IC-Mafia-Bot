import discord
from discord import ui
from . import quirk_logic
import logging

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

class QuirkReviewView(ui.View):
    """Approve/Reject buttons for individual quirks."""
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.target_user_id = user_id

    @ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        # Safeguard for permissions (especially if checked outside guild)
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
        # 1. Save to pending queue (This handles the overwrite logic)
        quirk_logic.queue_pending_quirk(interaction.user.id, self.quirk_input.value)
        
        # 2. Alert admins - FIX: Use client.get_channel so it works in DMs!
        admin_chan = interaction.client.get_channel(self.admin_channel_id)
        
        if admin_chan:
            old_quirk = quirk_logic.get_user_quirk(interaction.user.id)
            embed = discord.Embed(title="New Quirk Submitted", color=discord.Color.blue())
            embed.add_field(name="User", value=interaction.user.mention)
            
            # Show the overwrite context for admins
            if old_quirk:
                embed.add_field(name="Old Quirk", value=f"*{old_quirk}*", inline=False)
                embed.add_field(name="New Overwrite", value=f"**{self.quirk_input.value}**", inline=False)
            else:
                embed.add_field(name="Submission", value=self.quirk_input.value, inline=False)
                
            await admin_chan.send(embed=embed)
        
        await interaction.response.send_message("Submitted for review! I'll DM you once an admin decides. 😘", ephemeral=True)