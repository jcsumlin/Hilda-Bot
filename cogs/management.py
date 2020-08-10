import os
from datetime import datetime

import discord
import git
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands
from loguru import logger
from pytz import utc

from .utils.dataIO import dataIO


class Management(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        scheduler = AsyncIOScheduler(timezone=utc)
        scheduler.add_job(self.backupDatabase, 'interval', days=1, replace_existing=True,
                          coalesce=True, )
        scheduler.start()
        self.approvedChannels = dataIO.load_json("data/server/allowed_channels.json")

    async def commandError(self, message, channel):
        embed = discord.Embed(title="Command Error!",
                              description=message,
                              color=0xff0007)
        sent_message = await self.bot.send_message(channel, embed=embed)
        return sent_message

    async def commandSuccess(self, title, desc, channel):
        embed = discord.Embed(title=title, description=desc, color=0x00df00)
        await self.bot.send_message(channel, embed=embed)


    async def backupDatabase(self):
        logger.info("=====Start Database backup=====")
        FilePath = './cogs/database.db'  # replace the temp with your file path/name
        modifiedTime = os.path.getmtime(FilePath)

        timeStamp = datetime.fromtimestamp(modifiedTime).strftime("%b-%d-%y-%H:%M:%S")
        await os.rename(FilePath, './cogs/backup/database' + "_" + timeStamp + '.db')
        logger.success("=====Database Backup Complete!=====")

    @commands.command()
    async def update(self, ctx):
        if ctx.message.author.id == 204792579881959424 or ctx.message.author.id == 169983837168861184:
            git_dir = "./"
            try:
                g = git.cmd.Git(git_dir)
                updates = g.pull()
                embed = discord.Embed(title="Successfully pulled from repository", color=0x00df00, description=f"```{updates}```")
                await ctx.message.channel.send(embed=embed)
            except Exception as e:
                errno, strerror = e.args
                embed = discord.Embed(title="Command Error!",
                                      description=f"Git Pull Error: {errno} - {strerror}",
                                      color=0xff0007)
                await ctx.send(embed=embed)
        else:
            await ctx.message.channel("You don't have access to this command!")

    @commands.has_role("Staff")
    @commands.group()
    async def response(self, ctx):
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(title="That's not how you use that command!",
                                  color=discord.Color.red())
            embed.add_field(name="!response add [channel]",
                            value="Adds a channel to the list of channels users can user commands in.")
            embed.add_field(name="!response remove [channel]",
                            value="Removes a channel to the list of channels users can user commands in.")
            embed.add_field(name="!response list",
                            value="Displays the list of channels users can user commands in.")
            await ctx.send(embed=embed)

    @response.command(name="add")
    async def _add(self, ctx, channel: discord.TextChannel = None):
        if channel == None:
            await self.commandError(
                "That's not how you use that command!: `!response add #channel-to-add`",
                ctx.message.channel)
        else:
            channel_id = channel.id
            if channel_id in self.approvedChannels:
                await self.commandError("That channel is already in the list!", ctx.message.channel)
                return
            self.approvedChannels.append(channel_id)
            try:
                dataIO.save_json("data/server/allowed_channels.json", self.approvedChannels)
                await self.commandSuccess("Success!",
                                          f"Successfully added channel #{channel.name} to the allowed list! Users will now be able to use commands here!",
                                          ctx.message.channel)
            except:
                await self.commandError("Error while saving channel to file!!", ctx.message.channel)

    @response.command(name="remove")
    async def _remove(self, ctx, channel: discord.TextChannel = None):
        if channel == None:
            embed = discord.Embed(title="That's not how you use that command!",
                                  description="!response remove #channel-to-delete",
                                  color=discord.Color.red())
            await ctx.send(embed=embed)
        else:
            channel_id = channel.id
            if channel_id in self.approvedChannels:
                self.approvedChannels.remove(channel_id)
                try:
                    dataIO.save_json("data/server/allowed_channels.json", self.approvedChannels)
                    embed = discord.Embed(
                        title=f"Successfully removed channel #{channel.name} from the allow commands list!",
                        color=discord.Color.green())
                    await ctx.send(embed=embed)
                except:
                    embed = discord.Embed(title="Error while saving file!!",
                                          color=discord.Color.red())
                    await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="Channel is not in the list!",
                                      color=discord.Color.red())
                await ctx.send(embed=embed)

    @response.command(name="list")
    async def _list(self, ctx):
        embed = discord.Embed(title="List of channels users can use commands in.")
        for channel in self.approvedChannels:
            channel = self.bot.get_channel(int(channel))
            if channel is None:
                continue
            embed.add_field(name=f"{channel.name}",
                            value=f"ID: {channel.id}",
                            inline=False)
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Management(bot))
