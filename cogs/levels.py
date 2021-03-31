from typing import Union

import discord
from discord.ext import commands
from pymongo import MongoClient

client = MongoClient("mongodb+srv://rstar284:LemmeConnectPls@pydb.hbwzt.mongodb.net/test?retryWrites=true&w=majority")
# No one saw that!

leveling = client['discord']['leveling']


class level(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print("ready!")

    @commands.Cog.listener()
    async def on_message(self, message):
        stats = leveling.find_one({"id": message.author.id})
        if not message.author.bot:
            if stats is None:
                newuser = {"id": message.author.id, "xp": 100}
                leveling.insert(newuser)
            else:
                xp = stats["xp"] + 5
                leveling.update_one({"id": message.author.id}, {"$set": {"xp": xp}})
                lvl = 0
                while True:
                    if xp < ((50 * (lvl ** 2)) + (50 * (lvl - 1))):
                        break
                    lvl += 1
                xp -= ((50 * ((lvl - 1) ** 2)) + (50 * (lvl - 1)))
                if xp == 0:
                    await message.channel.send(
                        f"woah {message.author.mention}! You leveled up to **level: {lvl}**!!")

    @commands.command()
    async def rank(self, ctx, *, user: Union[discord.Member, discord.User] = None):
        if ctx.author.id == "755810994739085414":
            return ctx.channel.send("Mari, you are hereby not allowed to use the leveling system :)")
        user = user or ctx.author
        stats = leveling.find_one({"id": user.id})
        if stats is None:
            embed = discord.Embed(
                description="ERROR: USER HAS SENT 0 MESSAGES", color=discord.Colour.red)
            await ctx.channel.send(embed=embed)
        else:
            xp = stats["xp"]
            lvl = 0
            rank = 0
            while True:
                if xp < ((50 * (lvl ** 2)) + (50 * (lvl - 1))):
                    break
                lvl += 1
            xp -= ((50 * ((lvl - 1) ** 2)) + (50 * (lvl - 1)))
            boxes = int((xp / (200 * ((1 / 2) * lvl))) * 20)
            rankings = leveling.find().sort("xp", -1)
            for x in rankings:
                rank += 1
                if stats["id"] == x["id"]:
                    break
            embed = discord.Embed(title="{0}'s level stats".format(user.name))
            embed.add_field(name='Name', value=user.mention, inline=True)
            embed.add_field(name='XP', value=f"{xp}/{int(200 * ((1 / 2) * lvl))}", inline=True)
            embed.add_field(name='Rank', value=f"{rank}/{ctx.guild.member_count}", inline=True)
            embed.add_field(name='Progress [lvl]',
                            value=boxes * ":blue_square:" + (20 - boxes) * ":white_large_square:")
            embed.set_thumbnail(url=user.avatar_url)
            await ctx.send(embed=embed)

    @commands.command()
    async def leaderboard(self, ctx):
        if ctx.author.id == "755810994739085414":
            return ctx.channel.send("Mari, you are hereby not allowed to use the leveling system :)")
        rankings = leveling.find().sort("xp", -1)
        i = 1
        embed = discord.Embed(title="Rankings")
        for x in rankings:
            try:
                temp = ctx.guild.get_member(x["id"])
                tempxp = x["xp"]
                embed.add_field(name=f"{i}: {temp.name}", value=f"Total XP: {tempxp}", inline=False)
                i += 1
            except:
                pass
            if i == 11:
                break
        await ctx.channel.send(embed=embed)


def setup(bot):
    bot.add_cog(level(bot))
