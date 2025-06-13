import discord
import asyncio
import json
from discord.ext import commands
import mafiaconfig as config
# Get the same logger instance as in mafiabot.py
import logging

logger = logging.getLogger('discord')

class Narration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.story_channel_id = config.STORY_CHANNEL_ID

    async def send_narrative(self, narrative_parts):
        """
        Receives narrative parts from engine.py and actions.py,
        constructs the full narrative, and sends it to the story channel.
        """
        story_channel = self.bot.get_channel(self.story_channel_id)
        if story_channel:
            full_narrative = "\n".join(narrative_parts)
            await story_channel.send(full_narrative)
        else:
            print(f"Error: Story channel with ID {self.story_channel_id} not found.")

    @commands.Cog.listener()
    async def on_ready(self):
        print('Narration cog is ready.')

async def setup(bot):
    await bot.add_cog(Narration(bot))
