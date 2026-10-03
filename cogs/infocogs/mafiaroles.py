# cogs/infocogs/mafiaroles.py
import logging
from collections import Counter, defaultdict
import discord

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def show_roles_command(self, interaction: discord.Interaction):
    """Displays a public list of all roles, including alive/total counts."""
    logger.info(f"'/mafiaroles' command invoked by {interaction.user.name}.")
    game = getattr(self.bot, 'game_instance', None) or getattr(self, 'game', None)
    if not game or not game.game_roles:
        logger.warning("'/mafiaroles' command failed: No active game or roles not assigned.")
        await interaction.response.send_message("No game is running or roles have not been assigned yet.", ephemeral=True)
        return

    total_role_counts = Counter(role.name for role in game.game_roles)
    alive_role_counts = Counter(
        p.role.name for p in game.players.values() if p.is_alive and p.role
    )
    roles_by_alignment = defaultdict(list)
    for role_name, total_count in total_role_counts.items():
        alive_count = alive_role_counts[role_name]
        sample_role = next((r for r in game.game_roles if r.name == role_name), None)
        if sample_role:
            alignment = sample_role.alignment
            if alive_count == 0:
                role_str = f"- ~~{role_name}~~ _Alive: 0 / Total: {total_count}_"
            else:
                role_str = f"- {role_name} _Alive: {alive_count} / Total: {total_count}_"
            roles_by_alignment[alignment].append(role_str)

    embed = discord.Embed(
        title=f"Roles for Game #{game.game_settings.get('game_id', 'N/A')}",
        description=f"There are **{len(game.players)}** players in this game.",
        color=discord.Color.dark_teal()
    )
    for alignment, roles in sorted(roles_by_alignment.items()):
        if roles:
            embed.add_field(name=f"--- {alignment} ---", value="\n".join(sorted(roles)), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=False)
    logger.info(f"Successfully sent role list to {interaction.user.name}.")

