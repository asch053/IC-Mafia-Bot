# cogs/infocogs/mafiaroles.py
"""
Mafia Roles Slash Command (`/mafiaroles`).

Displays a public embed showing:
- Total role counts generated for the current match.
- How many players of each role are still alive vs. eliminated (with eliminated roles struck through).
- Displays themed skin titles alongside canonical names (e.g., `Relationship Detective (Town Cop)`).
- Organizes roles neatly by faction alignment (Town, Mafia, Neutral).
"""

import logging
from collections import Counter, defaultdict
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def show_roles_command(self, interaction: discord.Interaction):
    """
    Handles the `/mafiaroles` slash command.
    Generates an embed breaking down active roles by faction and living status.
    """
    logger.info(f"'/mafiaroles' command invoked by {interaction.user.name}.")
    game = getattr(self.bot, 'game_instance', None) or getattr(self, 'game', None)

    # 1. Guard against command invocation outside an active game
    if not game or not game.game_roles:
        logger.warning("'/mafiaroles' command failed: No active game or roles not assigned.")
        await interaction.response.send_message(
            "No game is running or roles have not been assigned yet.",
            ephemeral=True
        )
        return

    # 2. Count total roles created vs living instances
    total_role_counts = Counter(role.name for role in game.game_roles)
    alive_role_counts = Counter(
        p.role.name for p in game.players.values() if p.is_alive and p.role
    )

    # 3. Categorize roles by faction alignment
    roles_by_alignment = defaultdict(list)
    for role_name, total_count in total_role_counts.items():
        alive_count = alive_role_counts[role_name]
        sample_role = next((r for r in game.game_roles if r.name == role_name), None)
        if sample_role:
            alignment = sample_role.alignment
            disp_name = getattr(sample_role, 'display_name', role_name)

            # Format: Show themed display name and canonical role in parentheses if reskinned
            name_str = f"**{disp_name}** ({role_name})" if disp_name != role_name else f"**{role_name}**"

            # Strike through completely eliminated roles
            if alive_count == 0:
                role_str = f"- ~~{name_str}~~ _Alive: 0 / Total: {total_count}_"
            else:
                role_str = f"- {name_str} _Alive: {alive_count} / Total: {total_count}_"

            roles_by_alignment[alignment].append(role_str)

    # 4. Construct Discord embed
    embed = discord.Embed(
        title=f"Roles for Game #{game.game_settings.get('game_id', 'N/A')}",
        description=f"There are **{len(game.players)}** players in this game.",
        color=discord.Color.dark_teal()
    )
    for alignment, roles in sorted(roles_by_alignment.items()):
        if roles:
            embed.add_field(name=f"--- {alignment} ---", value="\n".join(sorted(roles)), inline=False)

    # 5. Deliver public response
    await interaction.response.send_message(embed=embed, ephemeral=False)
    logger.info(f"Successfully sent role list to {interaction.user.name}.")
