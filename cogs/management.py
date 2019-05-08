import discord
from discord.ext import commands
import git
import asyncio



class Management:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    def update(self, ctx):
        if ctx.message.author.id == 204792579881959424 or ctx.message.author.id == 169983837168861184:
            git_dir = "./"
            try:
                g = git.cmd.Git(git_dir)
                g.pull()
                embed = discord.Embed(title="Successfully pulled from repository", color=0x00df00)
                await self.bot.send_message(ctx.message.channel, embed=embed)
            except Exception as e:
                errno, strerror = e.args
                embed = discord.Embed(title="Command Error!",
                                      description=f"Git Pull Error: {errno} - {strerror}",
                                      color=0xff0007)
                await self.bot.send_message(ctx.message.channel, embed=embed)
        else:
            await ctx.message.channel.send("You don't have access to this command!")