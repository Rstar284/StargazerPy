import discord
from discord.ext import commands

class StarCraft(commands.cog):
    def __init__(self):
        self.bot = bot

def setup(bot):
    bot.add_cog(StarCraft(bot))

