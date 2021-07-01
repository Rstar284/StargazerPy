from discord.ext import commands
import discord


class Fun(commands.Cog):
    """
    Provides Fun commands to use in the bot
    """
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def repeattext(self, ctx):
        await ctx.reply("Sorry cannot work without my freinds py package, SURE I COULD MAKE MY OWN, but im lazy Ok? :sunglasses:")

def setup(bot):
    bot.add_cog(Fun(bot))
