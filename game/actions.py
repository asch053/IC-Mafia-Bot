#game/actions.py
"""A module for game actions and commands in the Mafia game bot."""
import logging
import random  
import logging
import json
import discord
from discord.ext import commands
import config
import utils.utilities as utils
from game.engine import Game
from game.player import Player
from game.roles import GameRole
# Get the same logger instance as in mafiabot.py
logger = logging.getLogger('discord')

