import discord
from discord.ext import commands
import aiohttp
from discord.ext.commands.context import Context

class MC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
    
    @commands.command()
    def mcserver(ctx, server: str):
        print("hi")

def setup(bot):
    bot.add_cog(MC(bot))