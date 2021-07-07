import discord
from discord.ext import commands

class Test(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot

    @commands.is_owner()
    @commands.command(hidden=True)
    async def testjoin(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        self.bot.dispatch("member_join", member)
    
    @commands.is_owner()
    @commands.command(hidden=True)
    async def broken(self, ctx: commands.context):
        await ctx.reply("Ok, i will error now")
        raise discord.errors.DiscordException
    
def setup(bot: discord.Client):
    bot.add_cog(Test(bot))
