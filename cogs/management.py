import discord
from discord.ext import commands
import git
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
from datetime import timedelta, time, datetime
from pytz import utc
from loguru import logger
import asyncore



class Management:
    def __init__(self, bot):
        self.bot = bot
        scheduler = AsyncIOScheduler(timezone=utc)
        scheduler.add_job(self.backupDatabase, 'interval', days=1, replace_existing=True,
                          coalesce=True, )
        scheduler.start()


    async def backupDatabase(self):
        logger.info("=====Start Database backup=====")
        FilePath = './cogs/database.db'  # replace the temp with your file path/name
        modifiedTime = os.path.getmtime(FilePath)

        timeStamp = datetime.fromtimestamp(modifiedTime).strftime("%b-%d-%y-%H:%M:%S")
        await os.rename(FilePath, './cogs/backup/database' + "_" + timeStamp + '.db')
        logger.success("=====Database Backup Complete!=====")

    @commands.command(pass_context=True)
    async def update(self, ctx):
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
            
def setup(bot):
    bot.add_cog(Management(bot))
