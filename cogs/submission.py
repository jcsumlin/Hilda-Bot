import asyncio
import configparser
import datetime
import json
import math
import os
import random
import re
import time
from datetime import timedelta, time, datetime

import discord
import requests
import simplejson as json
# SQLalchemy stuff
import sqlalchemy
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
from discord.ext import commands
from loguru import logger
# scheduling stuff
from sqlalchemy import create_engine, and_
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

# declaration for User class is in here
from cogs.utils.create_databases import Base, User, Content, SpecialEvents
from .utils.chat_formatting import escape
from .utils.dataIO import dataIO


class Submission(commands.Cog):

    def __init__(self, bot):
        self.submission_triggers = ["submit"]
        self.bot = bot
        engine = create_engine('sqlite:///database.db')
        Base.metadata.bind = engine
        DBSession = sessionmaker(bind=engine)
        self.session = DBSession()  # session.commit() to store data, and session.rollback() to discard changes
        self.scheduler = AsyncIOScheduler(timezone='America/New_York')
        self.scheduler.add_job(self.housekeeper, trigger='cron', hour=23, minute=1, second=1, replace_existing=True,
                               coalesce=True)
        self.scheduler.add_job(self.setGame, 'interval', seconds=10, replace_existing=True, coalesce=True)
        self.scheduler.start()
        self.auth = configparser.ConfigParser()
        self.auth.read('../auth.ini')
        self.messageSetting = 0
        self.approvedChannels = dataIO.load_json("data/server/allowed_channels.json")
        self.bannedXPChannels = dataIO.load_json("data/xp/banned_channels.json")
        self.epoch = datetime.utcfromtimestamp(0)
        self.testServerIds = [553739065074253834, 593887030216228973, 556208599794450434,
                              670472297504833546]  # Always allow commands here

    async def setGame(self):
        if self.messageSetting == 0:
            members = 0
            for guild in self.bot.guilds:
                for member in guild.members:
                    members += 1
            self.messageSetting = 1
            await self.bot.change_presence(activity=discord.Game(name=f'!help | Helping {members} members',
                                                                 url='https://www.patreon.com/botboi',
                                                                 type=1))

        elif self.messageSetting == 1:
            await self.bot.change_presence(activity=discord.Game(name='!help | www.patreon.com/botboi',
                                                                 url='https://www.patreon.com/botboi',
                                                                 type=1))
            self.messageSetting = 0

    async def commandError(self, message, channel):
        embed = discord.Embed(title="Command Error!",
                              description=message,
                              color=0xff0007)
        sent_message = await channel.send(embed=embed)
        return sent_message

    async def commandSuccess(self, title, channel, desc=""):
        embed = discord.Embed(title=title, description=desc, color=0x00df00)
        return await channel.send(embed=embed)

    @commands.has_role("Staff")
    @commands.command()
    async def listjobs(self, ctx):
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            logger.info(job)
            await ctx.send(job)

    @commands.has_role("Staff")
    @commands.command()
    async def backup(self, ctx):
        if await self.checkChannel(ctx):
            content = self.session.query(Content).all()
            with open("../backup.csv", "w") as f:
                f.write("Submission ID,Message ID,User's Name,Date Posted,Link,Score,Comment,XP From Content,Event\n")
                for row in content:
                    if row.event_id is not None:
                        event = self.session.query(SpecialEvents).filter_by(id=int(row.event_id)).one()
                        event = event.name
                    else:
                        event = "N/A"
                    f.write(str(row.submission_id) + ',' + str(row.message_id)
                            + ',' + str(row.user) + ',' + str(row.datesubmitted) + ',' + str(row.link)
                            + ',' + str(row.score) + ',' + str(row.comment) + ',' +
                            str(row.xpfromcontent) + ',' + str(event) + "\n")
            embed = discord.Embed(title="Backup Complete!", color=0x00ff00)
            await ctx.send(ctx.message.channel, embed=embed)
            await self.bot.send_file(ctx.message.author, '../backup.csv')
            logger.success("Done")
            os.remove('../backup.csv')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.content.startswith(
                '!') == False and message.channel.id not in self.bannedXPChannels or message.guild.id in self.testServerIds:
            # If this message is not a command and is not in the list of channels users CANNOT gain XP from chatting
            db_user = await self.getDBUser(str(message.author.id))
            if db_user != None:
                xp = int(len(message.content.split()) * 0.5)
                if xp == 0:
                    return
                await self.giveXP(db_user, xp)
                await self.levelup(message)
            else:
                await self.register(message)

    def check_reaction(self, message, reaction):
        submit_command = False
        for trigger in self.submission_triggers:
            if message.content.startswith("!" + trigger):
                submit_command = True
        return reaction.id == int(self.auth.get('discord', 'KUDOS_REACTION_ID')) and submit_command

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        reaction = payload.emoji
        message_id = payload.message_id
        guild_id = payload.guild_id
        guild = discord.utils.find(lambda g: g.id == guild_id, self.bot.guilds)
        channel = discord.utils.get(guild.channels, id=payload.channel_id)
        message = await channel.fetch_message(id=message_id)
        userToUpdate = discord.utils.get(guild.members, id=payload.user_id)
        try:
            if isinstance(reaction, discord.PartialEmoji):
                # <:HildaNice:554394104117723136>

                if self.check_reaction(message, reaction):
                    # logger.debug("reaction added " + user.name + " " + str(reaction.emoji))
                    # find user in database using id
                    db_user = self.session.query(User).filter(User.id == payload.user_id).one()
                    content_author = self.session.query(Content).filter(Content.message_id == message_id).one()
                    # increase adores by 1 and xp
                    db_user.adores += 1
                    db_user.currentxp += 20
                    content_author.score += 1
                    # commit session
                    self.session.commit()
                    logger.debug(
                        f"Reaction successfully added from {message_id}. Score: {content_author.score}, Adores: {db_user.adores}, XP: {db_user.currentxp}")
        except:
            logger.error("Adding reaction broke for user " + userToUpdate)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        reaction = payload.emoji
        message_id = payload.message_id
        guild_id = payload.guild_id
        guild = discord.utils.find(lambda g: g.id == guild_id, self.bot.guilds)
        channel = discord.utils.get(guild.channels, id=payload.channel_id)
        message = await channel.fetch_message(id=message_id)
        userToUpdate = discord.utils.get(guild.members, id=payload.user_id)
        # logger.debug("reaction added " + user.name + " " + str(reaction.emoji))
        try:
            # logger.debug("reaction added " + user.name + " " + str(reaction.emoji))
            if isinstance(reaction, discord.PartialEmoji):
                # logger.debug("reaction added " + user.name + " " + str(reaction.emoji))
                if self.check_reaction(message, reaction):
                    # logger.debug(f"reaction removed {user.name} : {reaction.emoji}")
                    # find user in database using id
                    db_user = self.session.query(User).filter(User.id == str(payload.user_id)).one()
                    content_author = self.session.query(Content).filter(Content.message_id == str(message_id)).one()
                    # increase adores by 1 and xp
                    db_user.adores -= 1
                    db_user.currentxp -= 20
                    content_author.score -= 1
                    # commit session
                    self.session.commit()
                    logger.debug(
                        f"Reaction successfully removed from {message_id}. Score: {content_author.score}, Adores: {db_user.adores}, XP: {db_user.currentxp}")
        except:
            logger.error(f"Removing reaction from {reaction.message.id} broke.")

    async def getDBUser(self, userID: str):  # gets the database user based on the user's ID
        db_user = None  # return none if we can't find a user
        if userID != "426541567092850703" and userID != "525814724567367682":
            try:  # try to find user in database using id
                db_user = self.session.query(User).filter_by(id=userID).one_or_none()
            except sqlalchemy.orm.exc.NoResultFound:
                logger.error(f'No user found, probably not registered {userID}')
            except sqlalchemy.orm.exc.MultipleResultsFound:
                logger.error('Multiple users found, something is really broken!')
            return db_user  # this value will be None or a valid user, make sure to check

    async def getDBUserbyUserID(self, user_id):  # gets the database user based on the user's ID
        db_user = None  # return none if we can't find a user
        try:  # try to find user in database using id
            db_user = self.session.query(User).filter(User.id == user_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            logger.error(f'No user found, probably not registered {user_id}')
        except sqlalchemy.orm.exc.MultipleResultsFound:
            logger.error('Multiple users found, something is really broken!')
        return db_user  # this value will be None or a valid user, make sure t

    async def linkSubmit(self, message, userToUpdate, comment, event_id: int = False):
        url_pattern = "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        url = re.search(url_pattern, message.content.lower()).group(0)
        logger.debug('link submitting for ' + str(userToUpdate.name))
        logger.debug(str(userToUpdate.name) + "'s url - " + url)
        await self.handleSubmit(message, userToUpdate, url, comment, event_id=event_id)

    @commands.command()
    async def leaderboard(self, ctx):
        if await self.checkChannel(ctx):
            leaderboard = self.session.query(User).filter(User.server_id == str(ctx.message.guild.id)).order_by(
                User.level.desc(), User.currentxp.desc()).limit(10)
            embed = discord.Embed(title="__**Leaderboard**__", thumbnail=ctx.message.guild.icon,
                                  description="The top 10 users of this server!", colour=0xb2cefe)
            for user in leaderboard:
                if user is None:
                    continue
                try:
                    member = ctx.message.guild.get_member(int(user.id))
                except Exception as e:
                    member = user
                    pass
                if member is None:
                    member = user
                embed.add_field(
                    name=":black_small_square: " + escape(member.name, formatting=True) + f"  Level: {user.level} | XP: {user.currentxp}",
                    value="==========", inline=False)

            await ctx.send(ctx.message.channel, embed=embed)

    @commands.command()
    async def submit(self, ctx):
        if ctx.channel.id in [780685976413667349,780691485577576520] or ctx.message.guild.id in self.testServerIds:
            if ("https://" in ctx.message.content.lower() or "http://" in ctx.message.content.lower()):
                # do linksubmit
                message = ctx.message.content[7:].lstrip(" ")
                if message.startswith('https://') or message.startswith('http://'):
                    comment = ""
                else:
                    comment = re.search("([a-zA-Z\s]+) (https?:\/\/)", message).group(1)

                await self.linkSubmit(ctx.message, ctx.message.author, comment)
            else:
                try:
                    # normal submit.
                    comment = ctx.message.content[7:].lstrip(" ")
                    await self.normalSubmit(ctx.message, ctx.message.author, comment)
                except:
                    pass
        else:
            await self.commandError("Please go to either <#780685976413667349> or <#780691485577576520> to use this command!", ctx.channel)

    @commands.command()
    async def streakwarning(self, ctx, setting=None):
        if await self.checkChannel(ctx):
            db_user = await self.getDBUser(str(ctx.message.author.id))
            if db_user != None:
                if setting == None:
                    await self.commandError(
                        "Please specify the status of your level up messages. !streakwarning [on | off]",
                        ctx.message.channel)
                    return

                elif setting.lower() == 'on':
                    db_user.decaywarning = True
                    self.session.commit()
                    await ctx.send(f"```diff\n+ Decay warning notification for {ctx.message.author} are now on!\n```")
                elif setting.lower() == 'off':
                    db_user.decaywarning = False
                    self.session.commit()
                    await ctx.send(f"```diff\n+ Decay warning notification for {ctx.message.author} are now off!\n```")

    @commands.command()
    async def levelwarning(self, ctx, setting=None):
        if await self.checkChannel(ctx):
            channel = ctx.message.channel.id
            server_id = ctx.message.guild.id
            db_user = await self.getDBUser(str(ctx.message.author.id))
            if db_user != None:
                if setting == None:
                    await self.commandError(
                        "Please specify the status of your level up messages. !levelwarning {on | off}",
                        ctx.message.channel)
                    return

                elif setting.lower() == 'on':
                    db_user.levelnotification = True
                    self.session.commit()
                    await ctx.send(f"```diff\n+ Level up notification for {ctx.message.author} are now on!\n```")
                elif setting.lower() == 'off':
                    db_user.levelnotification = False
                    self.session.commit()
                    await ctx.send(f"```diff\n+ Level up notification for {ctx.message.author} are now off!\n```")


    @commands.command()
    async def stats(self, ctx, user: discord.Member = None):
        if await self.checkChannel(ctx):
            # try to find user in database using id
            if user == None:
                db_user = await self.getDBUser(str(ctx.message.author.id))
                author = ctx.message.author

            else:
                db_user = await self.getDBUser(str(user.id))
                author = user
            # if we found the user in our spreadsheet
            if (db_user != None):
                stats = await self.getUserStats(db_user)
                # then extract individual stats for simplicity

                if user == None:
                    if ctx.message.author.nick != None:
                        name = ctx.message.author.nick
                    else:
                        name = ctx.message.author.name
                    roles = author.roles
                    top_role = "None"
                    levels = list(dict(self.auth.items('level-roles')).values())
                    for role in roles:
                        if role.name in levels:
                            top_role = role.name
                    stats_embed = discord.Embed(title=escape(name, formatting=True),
                                                description="{}, Level: {}".format(top_role, stats['level']),
                                                color=0x33cccc)
                    stats_embed.set_thumbnail(url=ctx.message.author.avatar_url)
                else:
                    if user.nick != None:
                        name = user.nick
                    else:
                        name = user.name
                    roles = author.roles
                    top_role = "None"
                    levels = list(dict(self.auth.items('level-roles')).values())
                    for role in roles:
                        if role.name in levels:
                            top_role = role.name
                    stats_embed = discord.Embed(title=escape(name, formatting=True),
                                                description="{}, Level: {}".format(top_role, stats['level']),
                                                color=0x33cccc)
                    pass
                stats_embed.add_field(name="Progress:", value=f"{stats['expbar']}", inline=False)
                stats_embed.add_field(name="**XP**:", value=f"{stats['xp']}/{stats['next_level_required_xp']}",
                                      inline=True)
                stats_embed.add_field(name="**Current Streak**:", value="{0}".format(stats['streak']), inline=True)
                stats_embed.add_field(name="**High Score**:", value="{0}".format(stats['highscore']), inline=True)
                stats_embed.add_field(name="**Kudos**:",
                                      value=f"{self.auth.get('discord', 'KUDOS_ID')} **Given**: {stats['adores_given']} | {self.auth.get('discord', 'KUDOS_ID')} **Received**: {stats['adores_gotten']}",
                                      inline=True)
                stats_embed.add_field(name="Stats",
                                      value=f"    **Submits**: {stats['total_submissions']} | **Tokens**: {stats['coins']}",
                                      inline=False)

                submit_status = f":regional_indicator_x: {'You' if user == None else 'They'} have not submitted today."

                # get the date of the expiry
                # Streak expires at 7am UTC on that day
                streak_expiration = db_user.expiry
                streak_expiration = datetime.combine(streak_expiration, time(6, 0))
                # and get now in UTC
                now = datetime.utcnow()
                # then compare the difference between those times
                delta = streak_expiration - now
                # get time difference
                d_days = delta.days
                if d_days < 0:
                    d_days = 0
                delta = delta.seconds
                d_sec = int(delta % 60)
                delta = delta - d_sec
                d_min = int((delta % 3600) / 60)
                delta = delta - (d_min * 60)
                d_hour = int(delta / 3600)

                submitted_today = 'yes' if db_user.submitted == 1 else 'no'
                adores = db_user.adores
                # stats_embed.add_field(name="Adores", value="{0}".format(adores))

                if submitted_today == 'yes':
                    submit_status = f":white_check_mark: {'You' if user == None else 'They'} have submitted today"
                else:
                    submit_status = f":regional_indicator_x: {'You' if user == None else 'They'} have not submitted today."
                # score_card = name_card + xp_card + adores_card + stats_card
                stats_embed.add_field(name="Submit Status", value=submit_status, inline=True)
                stats_embed.set_footer(text="Streaks Expires: {0} Days, {1} Hours, {2} Minutes, {3} Seconds.".format(
                    d_days, d_hour, d_min, d_sec))

                await ctx.send(embed=stats_embed)
            else:
                await ctx.send(
                    "```diff\n- I couldn't find your name in our database. Are you sure you're registered? If you are, contact an admin immediately.\n```")

    @commands.command()
    async def timeleft(self, ctx):
        if await self.checkChannel(ctx):
            now = datetime.utcnow()
            end = datetime(now.year, now.month, now.day, hour=3, minute=0, second=0, microsecond=0)
            difference = end - now
            seconds_to_work = difference.seconds
            difference_hours = math.floor(seconds_to_work / 3600)
            seconds_to_work = seconds_to_work - 3600 * difference_hours
            difference_minutes = math.floor(seconds_to_work / 60)
            seconds_to_work = seconds_to_work - 60 * difference_minutes
            jobs = self.scheduler.get_jobs()
            if difference_hours < 5:
                await ctx.send(
                    '```diff\n- {0} hours, {1} minutes, and {2} seconds left to submit for today!\n! Resets at 23:00 EST```'.format(
                        difference_hours, difference_minutes, seconds_to_work))
            else:
                await ctx.send(
                    '```diff\n+ {0} hours, {1} minutes, and {2} seconds left to submit for today!\n! Resets at 23:00 EST```'.format(
                        difference_hours, difference_minutes, seconds_to_work))


    async def register(self, message):
        curdate = datetime.utcnow()
        today = "{0}-{1}-{2}".format(curdate.month, curdate.day, curdate.year)
        already_registered = False
        # try to find user in database using id
        db_user = await self.getDBUser(str(message.author.id))

        # add a new user if there's no registered user
        if (db_user == None):
            # create new user object
            new_user = User(name=message.author.name,
                            server_id=str(message.guild.id),
                            level=1,
                            id=message.author.id,
                            startdate=curdate,
                            currency=0,
                            streak=0,
                            expiry=curdate,
                            submitted=False,
                            raffle=False,
                            promptsadded=0,
                            totalsubmissions=0,
                            currentxp=0,
                            adores=0,
                            highscore=0,
                            decaywarning=True,
                            levelnotification=True,
                            xptime=(datetime.utcnow() - self.epoch).total_seconds(),
                            special_event_submitted=False)
            # add to session
            self.session.add(new_user)

            self.session.commit()
            logger.success(f"Successfully registered {message.author.name}")
        else:
            logger.error(f"{message.author.name} is already registered!")


    @commands.has_role('Staff')
    @commands.command()
    async def fullreset(self, ctx, user: discord.User = None):
        if await self.checkChannel(ctx):
            if user == None:
                receiver = ctx.message.author
            elif user != None and isinstance(user, discord.User):
                receiver = user
            else:
                await ctx.send("```\n!fullreset {@user} to reset a user or !fullreset to reset yourself.\n```")
                return
            try:
                db_user = self.session.query(User).filter(User.id == str(receiver.id)).one()
                db_user.level = 1
                db_user.currency = 0
                db_user.streak = 0
                db_user.highscore = 0
                db_user.adores = 0
                db_user.currentxp = 0
                db_user.raffle = False
                db_user.submitted = False
                self.session.commit()
                logger.success(f"{ctx.message.author.name} reset {receiver.name}'s stats")
                await ctx.send("```Markdown\n#{0} stats have been fully reset\n```".format(receiver.name))
            except:
                await ctx.send("```Markdown\n#Something went wrong.\n```")
                self.session.rollback()

    @commands.has_role("Staff")
    @commands.command()
    async def deletesubmissions(self, ctx, user: discord.User = None):
        if await self.checkChannel(ctx):
            if user == None:
                await ctx.send("Please specify a user.")
            else:
                db_user = await self.getDBUser(str(user.id))
                if db_user == None:
                    return await ctx.send("User is not registered. They shouldn't have any submissions logged.")
                else:
                    content = len(self.session.query(Content).filter_by(user=str(user.id)).all())
                    if content > 0:
                        self.session.query(Content).filter_by(user=str(user.id)).delete()
                        self.session.commit()
                        await ctx.send(
                            f"ALL of {user.name}'s submissions have been removed from the database! Their stats will not have changed (use !fullreset [user] to reset them completly).")
                    else:
                        await ctx.send(f"{user.name} has no submissions to remove.")

    @commands.has_role("Staff")
    @commands.command()
    async def delete(self, ctx, user: discord.User = None):
        if await self.checkChannel(ctx):
            if user is None:
                await self.commandError(channel=ctx.message.channel,
                                        message="!delete [user] requires you to mention a discord user to delete their record in the database")
                return
            msg = await ctx.send('Are you sure you want to COMPLETELY erase this user?')
            await msg.add_reaction(u"\U0001F44D")
            await msg.add_reaction(u"\U0001F44E")

            def check(reaction, user):
                return str(reaction.emoji) in [u"\U0001F44D", u"\U0001F44E"] and user == ctx.message.author

            res = await self.bot.wait_for('reaction_add', check=check, timeout=15.0)
            if res[0].emoji == u"\U0001F44D":
                db_user = await self.getDBUser(str(user.id))
                if db_user != None:
                    try:
                        receiver = user
                        db_user = self.session.query(User).filter(User.id == str(receiver.id)).delete()
                        db_content = self.session.query(Content).filter(Content.user == str(receiver.id)).delete()
                        self.session.commit()
                        logger.success(f"User {user.name} has been deleted from the DB by {ctx.message.author.name}")
                        completed = await self.commandSuccess(channel=ctx.message.channel,
                                                              title="User Successfully Deleted",
                                                              desc="Users Stats and submissions have been removed from the Database.")
                        await msg.delete()
                        await completed.delete(delay=5)
                    except SQLAlchemyError as e:
                        logger.error(e)
                else:
                    await self.commandError("User's ID could not but found in the Database", ctx.message.channel)
            elif res[0].emoji == '👎':
                canceled = await ctx.send("Action canceled.")
                await msg.delete()
                await canceled.delete(delay=5)

            else:
                canceled = await ctx.send("Action canceled. [invalid reaction]")
                await msg.delete()
                await canceled.delete(delay=5)

    @commands.has_role("Staff")
    @commands.command()
    async def rollback(self, ctx, messageID=None):
        if await self.checkChannel(ctx):
            submission = self.getDBSubmission(str(messageID))
            if submission is None:
                await ctx.send(
                    "```diff\n- No such Submission. Make sure you are using the message ID of the submit post.\n```")
                return
            remove = self.removeDBSubmission(messageID)
            if remove is True:
                db_user = await self.getDBUser(str(submission.user))
                newscore = db_user.totalsubmissions - 1
                newcurrency = db_user.currency - 10
                current_streak = db_user.streak
                new_streak = current_streak - 1
                current_xp = db_user.currentxp
                xp_gained = 20 + int(math.floor(current_streak * 2))
                current_level = db_user.level
                new_xp_total = current_xp - xp_gained
                if new_xp_total < 0:  # decrease level
                    current_level = current_level - 1
                    next_level_required_xp = current_level * 15 + 50
                    new_xp_total = next_level_required_xp + new_xp_total
                    db_user.level = int(current_level)
                    db_user.currentxp = int(new_xp_total)

                # otherwise just increase exp
                else:
                    db_user.currentxp = int(new_xp_total)
                # update high score if it's higher
                if new_streak > db_user.highscore:
                    db_user.highscore = new_streak
                # write all new values to our cells
                db_user.totalsubmissions = newscore
                db_user.currency = newcurrency
                db_user.streak = new_streak
                if isinstance(submission.event_id, int) and submission.event_id is not None and submission.id >= 1:
                    event = self.session.query(SpecialEvents).filter_by(id=submission.event_id).one_or_none()
                    if event is not None:
                        db_user.special_event_submitted = False
                    else:
                        logger.warning("Could not find that event in the database!")
                else:
                    db_user.submitted = False
                # and push all cells to the database
                self.session.commit()
                await ctx.send("```diff\n+ Submission has been removed from the database.\n```")
                await self.updateRole(db_user.level, ctx.message)
            elif remove is False:
                await ctx.send("```diff\n- Error Removing Submission from database, check logs.\n```")

            else:
                await ctx.send("```diff\n- Error Removing Submission from DB, check logs.\n```")

    async def levelup(self, message):
        """
        :param message: discord message object
        :return:
        """
        db_user = await self.getDBUser(str(message.author.id))
        if db_user != None:
            stats = await self.getUserStats(db_user)
            xp = stats['xp']
            lvl_end = stats['next_level_required_xp']
            if xp > lvl_end:
                stats['level'] += 1
                db_user.level = int(stats['level'])
                db_user.currentxp = 0
                await self.updateRole(stats['level'], message)
                self.session.commit()
                if db_user.levelnotification != False:
                    await self.commandSuccess(
                        title=f'You Leveled Up! You are now level {str(stats["level"])}! :confetti_ball:',
                        desc='To turn off this notification do !levelwarning off in the designated bot channels.',
                        channel=message.author)
                    return
            else:
                await self.checkLevelRole(message, db_user.level)

    @commands.group()
    async def help(self, ctx):
        if await self.checkChannel(ctx) and ctx.invoked_subcommand is None:
            embed = discord.Embed(title="WumpusBot Help",
                                  description='Here is a list of all of the commands you can use! [Bot made by J\_C\_\_\_#8947]',
                                  color=0x90BDD4)
            embed.add_field(name="!help [module title]",
                            value="Use any of the module's title to see the help for just that section. (reduces spam)")
            # embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/503498544485892100.png")
            staff = False
            if True:
                role_names = [role.name for role in ctx.message.author.roles]
                if 'Staff' in role_names:
                    staff = True
            embed_admin = discord.Embed(title="Staff",
                                        description="These commands require the Staff role to be used",
                                        color=0x90BDD4)
            embed_admin.add_field(name="!delete [user]",
                                  value="Removes a user from the database (Staff only! VERY DANGEROUS)",
                                  inline=False)
            embed_admin.add_field(name="!fullreset", value="Sets a users stats to 0. (Staff only!)",
                                  inline=False)
            embed_admin.add_field(name="!deletesubmissions [user]",
                                  value="Removes a user's submissions from the database "
                                        "(Staff only! VERY DANGEROUS)",
                                  inline=False)
            embed_admin.add_field(name="!rollback [message id]",
                                  value="removes a submission from the DB and rolls back the xp "
                                        "gained from it. (Staff only!)",
                                  inline=False)
            embed_admin.add_field(name="!xp add #discord-channel",
                                  value="Adds a channel to the list of channels where users CANNOT "
                                        "gain xp from chatting or use commands (Staff only!)",
                                  inline=False)
            embed_admin.add_field(name="!xp remove #discord-channel",
                                  value="Removes channel from banned XP channels (Staff only!)",
                                  inline=False)
            embed_admin.add_field(name="!xp list",
                                  value="Lists the channels where users CANNOT gain XP or use commands"
                                        "gained from it. (Staff only!)",
                                  inline=False)
            embed_admin.add_field(name="!response add #discord-channel",
                                  value="Adds a channel to the list of channels where users can "
                                        "use bot commands(Staff only!)",
                                  inline=False)
            embed_admin.add_field(name="!response remove #discord-channel",
                                  value="Removes a channel to the list of channels where users can "
                                        "use bot commands(Staff only!)",
                                  inline=False)
            embed_admin.add_field(name="!response list",
                                  value="Lists the channels where users CANNOT gain XP or use commands"
                                        "gained from it. (Staff only!)",
                                  inline=False)
            embed_xp = discord.Embed(title="XP",
                                     description="All commands related to WumpusCord's leveling system",
                                     color=0x90BDD4)
            embed_xp.add_field(name="!leaderboard",
                               value="Shows you the top 10 users in in the server.",
                               inline=False)
            embed_xp.add_field(name="!stats", value="To see your current scorecard", inline=False)
            embed_xp.add_field(name="!levelwarning [on | off]",
                               value="To turn on or off the DM warning system about your leveling on the server."
                                     "command !levelwarning on or !levelwarning off.",
                               inline=False)
            embed_xp.add_field(name="!streakwarning [on | off]",
                               value="To turn on or off the PM warning system about your streak use the "
                                     "command !levelwarning on or !levelwarning off.",
                               inline=False)

            embed_content = discord.Embed(title="Content",
                                          description="All commands related to WumpusBot's content curration features",
                                          color=0x90BDD4)
            embed_content.add_field(name="!submit",
                                    value="To submit content, drag and drop the file (.png, .gif, .jpg) "
                                          "into discord and add '!submit' as a comment to it.",
                                    inline=False)
            embed_content.add_field(name="!submit [link]",
                                    value="If you'd like to submit via internet link, make sure you right click"
                                          " the image and select 'copy image location' and submit that URL using"
                                          " the !submit command.",
                                    inline=False)
            embed_content.add_field(name="!timeleft",
                                    value="The !timeleft command will let you know how much longer you have "
                                          "left to submit for the day!",
                                    inline=False)

            embed.set_footer(text="If you have any questions or concerns, please contact a Staff "
                                  "member.")
            try:
                await ctx.message.author.send(embed=embed)
                if staff:
                    await ctx.message.author.send(embed=embed_admin)
                await ctx.message.author.send(embed=embed_xp)
                await ctx.message.author.send(embed=embed_content)
            except discord.Forbidden:
                message = await self.commandError(
                    "Error sending !help in your DMs, are you sure you have them enabled for this server? (right click server -> Privacy Settings)",
                    ctx.message.channel)
                await asyncio.sleep(5)
                await message.delete()

    @commands.has_role("Staff")
    @help.command(name="staff")
    async def _staff(self, ctx):
        embed_admin = discord.Embed(title="Staff",
                                    description="These commands require the Staff role to be used",
                                    color=0x90BDD4)
        embed_admin.add_field(name="!delete [user]",
                              value="Removes a user from the database. Will ask for confirmation before any action is taken. (Staff only! VERY DANGEROUS)",
                              inline=False)
        embed_admin.add_field(name="!fullreset", value="Sets a users stats to 0. (Staff only!)",
                              inline=False)
        embed_admin.add_field(name="!deletesubmissions [user]",
                              value="Removes a user's submissions from the database "
                                    "(Staff only! VERY DANGEROUS)",
                              inline=False)
        embed_admin.add_field(name="!rollback [message id]",
                              value="removes a submission from the DB and rolls back the xp "
                                    "gained from it. (Staff only!)",
                              inline=False)
        embed_admin.add_field(name="!xp add #discord-channel",
                              value="Adds a channel to the list of channels where users CANNOT "
                                    "gain xp from chatting or use commands (Staff only!)",
                              inline=False)
        embed_admin.add_field(name="!xp remove #discord-channel",
                              value="removes a submission from the DB and rolls back the xp "
                                    "gained from it. (Staff only!)",
                              inline=False)
        embed_admin.add_field(name="!xp list",
                              value="Lists the channels where users CANNOT gain XP or use commands"
                                    "gained from it. (Staff only!)",
                              inline=False)
        try:
            await ctx.send(ctx.message.author, embed=embed_admin)
        except discord.Forbidden:
            message = await self.commandError(
                "Error sending !help staff in your DMs, are you sure you have them enabled for this server? (right click server -> Privacy Settings)",
                ctx.message.channel)
            await asyncio.sleep(5)
            await message.delete()

    @help.command(name="xp", )
    async def _xp(self, ctx):
        embed_xp = discord.Embed(title="XP",
                                 description="All commands related to WumpusCord's leveling system",
                                 color=0x90BDD4)
        embed_xp.add_field(name="!leaderboard",
                           value="Shows you the top 10 users in in the server.",
                           inline=False)
        embed_xp.add_field(name="!stats", value="To see your current scorecard", inline=False)
        embed_xp.add_field(name="!levelwarning [on | off]",
                           value="To turn on or off the DM warning system about your leveling on the server."
                                 "command !levelwarning on or !levelwarning off.",
                           inline=False)
        embed_xp.add_field(name="!streakwarning [on | off]",
                           value="To turn on or off the PM warning system about your streak use the "
                                 "command !levelwarning on or !levelwarning off.",
                           inline=False)
        try:
            await ctx.send(ctx.message.author, embed=embed_xp)
        except discord.Forbidden:
            message = await self.commandError(
                "Error sending !help xp in your DMs, are you sure you have them enabled for this server? (right click server -> Privacy Settings)",
                ctx.message.channel)
            await asyncio.sleep(5)
            await message.delete()

    @help.command(name="content", )
    async def _content(self, ctx):
        embed_content = discord.Embed(title="Content",
                                      description="All commands related to WumpusBot's content curation features",
                                      color=0x90BDD4)
        embed_content.add_field(name="!submit",
                                value="To submit content, drag and drop the file (.png, .gif, .jpg) "
                                      "into discord and add '!submit' as a comment to it.",
                                inline=False)
        embed_content.add_field(name="!submit [link]",
                                value="If you'd like to submit via internet link, make sure you right click"
                                      " the image and select 'copy image location' and submit that URL using"
                                      " the !submit command.",
                                inline=False)
        embed_content.add_field(name="!timeleft",
                                value="The !timeleft command will let you know how much longer you have "
                                      "left to submit for the day!",
                                inline=False)
        # embed_content.add_field(name="!randomidea",
        #                         value="Having trouble figuring out what to create?",
        #                         inline=False)
        # embed_content.add_field(name="!idea [idea]",
        #                         value="Add a random idea to the \"randomidea\" list!",
        #                         inline=False)
        try:
            await ctx.send(ctx.message.author, embed=embed_content)
        except discord.Forbidden:
            message = await self.commandError(
                "Error sending !help content in your DMs, are you sure you have them enabled for this server? (right click server -> Privacy Settings)",
                ctx.message.channel)
            await asyncio.sleep(5)
            await message.delete()


    @commands.has_role("Staff")
    @commands.group(name="xp")
    async def xp(self, ctx):
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(title="That's not how you use that command!",
                                  color=discord.Color.red())
            embed.add_field(name="!xp add [channel]",
                            value="Adds a channel to the list of channels users can NOT gain xp from.")
            embed.add_field(name="!xp remove [channel]",
                            value="Removes a channel to the list of channels users can NOT gain xp from.")
            embed.add_field(name="!xp list",
                            value="Displays the list of channels users can NOT gain xp from.")
            await ctx.send(embed=embed)

    @xp.command(name="add")
    async def _add(self, ctx, channel: discord.TextChannel = None):
        if channel == None:
            await self.commandError(
                "That's not how you use that command!: `!xp add #channel-to-add`",
                ctx.message.channel)
        else:
            channel_id = channel.id
            if channel_id in self.bannedXPChannels:
                await self.commandError("That channel is already in the banned list!",
                                        ctx.message.channel)
                return
            self.bannedXPChannels.append(channel_id)
            try:
                dataIO.save_json("data/xp/banned_channels.json", self.bannedXPChannels)
                await self.commandSuccess(title="Success!",
                                          desc=f"Successfully added channel {channel.name} to banned list! Users will no longer gain XP from chatting here!",
                                          channel=ctx.message.channel)
            except:
                await self.commandError("Error while saving channel to file!!",
                                        ctx.message.channel)

    @xp.command(name="remove")
    async def _remove(self, ctx, channel: discord.TextChannel = None):
        if channel == None:
            embed = discord.Embed(title="That's not how you use that command!",
                                  description="!xp remove #channel-to-delete",
                                  color=discord.Color.red())
            await ctx.send(embed=embed)
        else:
            channel_id = channel.id
            if channel_id in self.bannedXPChannels:
                self.bannedXPChannels.remove(channel_id)
                try:
                    dataIO.save_json("data/xp/banned_channels.json", self.bannedXPChannels)
                    embed = discord.Embed(
                        title=f"Successfully removed channel {channel.name} from the banned list!",
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

    @xp.command(name='list')
    async def _list(self, ctx):
        embed = discord.Embed(title="List of channels users can NOT gain XP in.")
        for channel in self.bannedXPChannels:
            embed.add_field(name=f"{self.bot.get_channel(channel).name}",
                            value=f"ID: {channel}",
                            inline=False)
        await ctx.send(embed=embed)

    async def submitLinktoDB(self, user, link, message_id, comments, xp_gained, event_id: int = False):
        try:
            new_content = Content()
            new_content.user = user.id
            new_content.datesubmitted = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            new_content.link = link
            new_content.score = 0
            new_content.message_id = message_id
            new_content.comment = comments
            new_content.xpfromcontent = xp_gained
            if isinstance(event_id, int) and event_id is not False and event_id >= 1:
                new_content.event_id = event_id
            self.session.add(new_content)
            self.session.commit()
            logger.success("added content to db")
        except Exception as e:
            logger.error(e)

    async def normalSubmit(self, message, userToUpdate, comment, event_id: int = False):
        logger.debug('submitting for ' + str(userToUpdate.name))
        try:
            url = message.attachments[0].url
        except:
            await self.commandError(
                "You need to submit something for this command to work! Use the !help command to see more info on how to use this command.",
                message.channel)
        logger.debug(str(userToUpdate.name) + "'s url - " + url)
        if isinstance(event_id, int) and event_id is not False and event_id >= 1:
            await self.handleSubmit(message, userToUpdate, url, comment, event_id)
        else:
            await self.handleSubmit(message, userToUpdate, url, comment)

    async def handleSubmit(self, message, userToUpdate, url, comment, event_id: int = False):
        curdate = datetime.utcnow()
        potentialstreak = curdate + timedelta(days=7)
        today = "{0}-{1}-{2}".format(curdate.month, curdate.day, curdate.year)
        streakdate = "{0}-{1}-{2}".format(potentialstreak.month, potentialstreak.day, potentialstreak.year)
        logger.debug('getting filepath to download for ' + str(userToUpdate.name))

        # try to find user in database using id
        db_user = await self.getDBUser(str(userToUpdate.id))

        # first find if we have  the user in our list

        if db_user is None:
            await message.send(message.channel,
                               "```diff\n- I couldn't find your name in our datavase. Are you sure you're registered? If you are, contact an admin immediately.\n```")
        else:
            # db_user is our member object
            # check if already submitted
            if db_user.submitted is True and event_id == False:
                logger.error(str(userToUpdate.name) + ' already submitted')
                await message.channel.send(message.channel,
                                           "```diff\n- You seem to have submitted something today already!\n```")
            elif db_user.special_event_submitted is True and isinstance(event_id, int) and event_id is not False:
                event = self.session.query(SpecialEvents).filter_by(id=event_id).one_or_none()
                if event is None:
                    logger.error(f'That Event ID is not in the database... Check your code: {event_id}')
                    return
                logger.error(str(userToUpdate.name) + f' already submitted [{event.name} event]')
                await message.channel.send(message.channel,
                                           f"```diff\n- You seem to have already submitted something for the {event.name} event today!\n```")
            # otherwise, do the submit
            else:
                # update all the stats
                newscore = db_user.totalsubmissions + 1
                newcurrency = db_user.currency + 10
                new_streak = int(db_user.streak) + 1
                current_xp = db_user.currentxp
                xp_gained = 20 + int(math.floor(new_streak * 2))
                current_level = int(db_user.level)
                next_level_required_xp = current_level * 15 + 50
                new_xp_total = current_xp + xp_gained
                # if we levelled up, increase level
                if new_xp_total >= next_level_required_xp:
                    current_level = current_level + 1
                    logger.debug("Checking Roles")
                    await self.updateRole(current_level, message)
                    new_xp_total = new_xp_total - next_level_required_xp
                    db_user.level = int(current_level)
                    db_user.currentxp = int(new_xp_total)
                    server_id = message.guild.id
                    if db_user.levelnotification == True:
                        await self.commandSuccess(
                            title=f'@{userToUpdate.name} Leveled Up! You are now level {str(current_level)}! :confetti_ball:',
                            desc='To turn off this notification do !levelwarning off in the designated bot channels.',
                            channel=userToUpdate)
                # otherwise just increase exp
                else:
                    db_user.currentxp = str(new_xp_total)
                # update high score if it's higher
                if new_streak > db_user.highscore:
                    db_user.highscore = new_streak
                # write all new values to our cells
                db_user.totalsubmissions = newscore
                db_user.currency = newcurrency
                db_user.streak = new_streak
                if isinstance(event_id, int) and event_id is not None and event_id >= 1:
                    db_user.special_event_submitted = int(self.auth.get('discord', 'LIVE'))
                else:
                    db_user.submitted = int(self.auth.get('discord', 'LIVE'))
                db_user.expiry = potentialstreak
                # and push all cells to the database
                self.session.commit()
                await self.submitLinktoDB(user=userToUpdate, link=url, message_id=str(message.id),
                                          comments=comment, xp_gained=xp_gained, event_id=event_id)
                await self.updateRole(db_user.level, message)
                await message.channel.send(
                    "```diff\n+ @{0} Submission Successful! Score updated!\n+ {1}xp gained.```".format(
                        userToUpdate.name, xp_gained))

    @commands.has_role("Staff")
    @commands.group(name="housekeeping", )
    async def housekeeing(self, ctx):
        try:
            await self.housekeeper(manual=True)
            await self.commandSuccess(title="Manual housekeeping completed!", desc="Users can now submit again :)",
                                      channel=ctx.message.channel)
        except Exception as e:
            await self.commandError(f"Error running housekeeper function: {e}", channel=ctx.message.channel)

    async def housekeeper(self, manual=False):
        curdate = datetime.utcnow()
        today = "{0}-{1}-{2}".format(curdate.month, curdate.day, curdate.year)

        # get all rows and put into memory
        members = self.session.query(User).all()
        logger.debug("Housekeeping on " + str(len(members)) + " rows on " + today)

        # reset all member's submitted status
        stmt = update(User).values(submitted=False)
        self.session.execute(stmt)
        stmt1 = update(User).values(special_event_submitted=False)
        self.session.execute(stmt1)

        self.session.commit()

        for curr_member in members:
            logger.debug('housekeeping member {0}'.format(curr_member.name))
            # Update in batch
            # set user in beginning if its needed to PM a user
            user = await self.bot.fetch_user(int(curr_member.id))
            if (user != None):
                # check for warning until streak decay begins
                days_left = (curr_member.expiry - curdate.date()).days
                if (curr_member.decaywarning == True and curr_member.streak > 0):
                    if (days_left == 3):
                        try:
                            await user.send(
                                "You have 3 days until your streak begins to expire!\nIf you want to disable these warning messages then enter the command !streakwarning off in the #bot-channel")
                        except:
                            logger.error('couldn\'t send 3day message')
                    elif (days_left == 1):
                        try:
                            await user.send(
                                "You have 1 day until your streak begins to expire!\nIf you want to disable these warning messages then enter the command !streakwarning off in the #bot-channel")
                        except:
                            logger.error('couldn\'t send 1day message')
            else:
                logger.error('User no longer visible to bot, must be gone')

            # If we're past the streak
            if ((curdate.date() - curr_member.expiry).days >= 0 and curr_member.streak > 0):

                pointReduce = pow(2, (curdate.date() - curr_member.expiry).days + 1)
                # reduce streak by 2^(daysPastStreak+1), until streak is zero
                logger.debug("Removing {0} points from {1}'s streak".format(pointReduce, curr_member.name))
                curr_member.streak = max(curr_member.streak - pointReduce, 0)
                # give a pm to warn about streak decay if member has left warnings on
                if (curr_member.decaywarning == True and user != None):
                    try:
                        await user.send(
                            "Your streak has decayed by {0} points! Your streak is now {1}.\nIf you want to disable these warning messages then enter the command !streakwarning off in the #bot-channel".format(
                                str(pointReduce), str(curr_member.streak)))
                    except:
                        logger.error('couldn\'t  send decay message')
        # commit all changes to the sheet at once
        self.session.commit()
        logger.success("housekeeping finished")
        if not manual:
            channel = self.bot.get_channel(761308316357754910)
            if channel is not None:
                await channel.send("Housekeeping has finished running. You may now !submit again!")

    def getDBSubmission(self, messageID):
        submission = None  # return none if we can't find a user
        try:  # try to find user in database using id
            submission = self.session.query(Content).filter(Content.message_id == messageID).one()
        except sqlalchemy.orm.exc.NoResultFound:
            logger.error('No submission found, probably does\'t exist.')
        except sqlalchemy.orm.exc.MultipleResultsFound:
            logger.error('Multiple submissions found, something is really broken!')
        return submission  # this value will be None or a valid user, make sure to check

    def removeDBSubmission(self, messageID):
        done = None  # return none if we can't find a user
        try:  # try to find user in database using id
            logger.debug("Removing submission {} from db".format(messageID))
            self.session.query(Content).filter(Content.message_id == messageID).delete()
            self.session.commit()
            done = True
            logger.success("Successfully removed {} from db.".format(messageID))
        except Exception as e:
            logger.error(e)
            pass
        return done  # this value will be None or a valid user, make sure to check

    @commands.command('levelcheck')
    async def levelCheck(self, ctx):
        db_user = await self.getDBUser(str(ctx.message.author.id))
        if db_user is not None:
            added_roles = await self.updateRole(db_user.level, ctx.message)
            if added_roles is not None and len(added_roles) > 0:
                embed = discord.Embed(title="Finished checking your roles!",
                                      description=f"**The roles that were added because of this check were:**\n{added_roles} ",
                                      color=discord.Color.green())
            else:
                embed = discord.Embed(title="Finished checking your roles!",
                                      description=f"All your roles are already up to date! No roles were added.",
                                      color=discord.Color.dark_orange())
            await ctx.send(embed=embed)
        else:
            await ctx.send("Could not find your user record!")

    async def updateRole(self, current_level, message: discord.Message):
        levels = []
        before_roles = message.author.roles
        for key in self.auth['level-roles']:
            level = re.search("^lvl_(\d+)$", key)
            levels.append(int(level.group(1)))

        after_roles = await self.buildAfterRoles(levels, current_level, message.guild)
        if after_roles is False:
            logger.exception(f"Failed to build 'after roles' for {message.author}")
            return
        if len(after_roles) == 0:
            return
        added_roles = (list(set(after_roles) - set(before_roles)))
        try:
            await message.author.add_roles(*added_roles)
        except Exception as e:
            logger.exception(f"Failed to add roles to {message.author.name}: {e}")
            return False
        role_string = ""
        for role in added_roles:
            role_string += role.name + " "
        logger.success(f"Successfully added {role_string} roles to {message.author.name}")
        return role_string

    async def buildAfterRoles(self, levels: list, max_level: int, guild):
        after_roles = []
        for level in levels:
            if max_level >= level:
                try:
                    role = discord.utils.get(guild.roles, name=self.auth['level-roles'][f'lvl_{level}'])
                except Exception as e:
                    logger.exception(f"Could not get role for afterRoles list: {e}")
                    return False
                if role is None:
                    logger.exception(f"Failed to find role with name {self.auth['level-roles'][f'lvl_{level}']}")
                    continue
                after_roles.append(role)
        return after_roles

    async def getUserStats(self, db_user):
        stats = {"user_id": str(db_user.id),
                 "user_name": db_user.name,
                 "total_submissions": db_user.totalsubmissions,
                 # TODO: total_pride_submissions will use the db_user.name since the
                 #  change to storing the useIDs rather than names was made after that event
                 "xp": db_user.currentxp,
                 "level": db_user.level,
                 "coins": db_user.currency,
                 "streak": db_user.streak,
                 "next_level_required_xp": (db_user.level * 15) + 50,
                 "percent": db_user.currentxp / ((db_user.level * 15) + 50),
                 "highscore": db_user.highscore,
                 "adores_given": db_user.adores}
        percent = stats['percent']

        expbar = ""
        blips = 20
        while percent > 0:
            expbar = expbar + '●'
            percent = percent - 0.05
            blips = blips - 1
        while blips > 0:
            expbar = expbar + '○'
            blips = blips - 1
        stats['expbar'] = expbar

        content_submitted = self.session.query(Content).filter(Content.user == stats['user_name']).all()
        adores = 0
        for content in content_submitted:
            adores += content.score
        stats['adores_gotten'] = adores
        return stats

    async def giveXP(self, db_user, xp: int):
        """
        Gives a user X amount of XP and updates their cooldown time. This is mostly used in the
        case of a user chatting.
        :param db_user: User object from database
        :param xp: int, amounnt of XP to give this user
        :return:
        """
        if db_user != None:
            time_diff = (datetime.utcnow() - self.epoch).total_seconds() - db_user.xptime
            if time_diff >= 30 or self.auth['discord']['LIVE'] == 0:
                # await self.getUserStats(db_user)
                try:
                    db_user.xptime = (datetime.utcnow() - self.epoch).total_seconds()
                    db_user.currentxp += int(xp)
                    self.session.commit()
                except Exception as e:
                    logger.error(f"Failed to give {db_user.username} {xp} XP! {e}")

    async def checkLevelRole(self, message: discord.Message, current_level: int):
        """

        :param message: discord message object
        :param current_level: int
        :return:
        """
        levels = []
        for key in self.auth['level-roles']:
            # logger.info(key)
            level = re.search("^lvl_(\d+)$", key)
            levels.append(int(level.group(1)))
        max_level = 0
        for level in levels:
            if current_level > level:
                max_level = level
            elif current_level < level:
                break
        if max_level != 0:
            role_name = self.auth.get('level-roles', f'lvl_{max_level}')
            role = discord.utils.get(message.guild.roles, name=role_name)
            if role is not None:
                if role in [y.name for y in message.author.roles]:
                    return
                else:
                    await message.author.add_roles(role)
            else:
                logger.error(f"The role {role_name} does not exist skipping.")

    async def on_command_error(self, error, ctx):
        if isinstance(error, commands.CommandOnCooldown):
            await self.commandError(channel=ctx.message.channel,
                                    message='This command is on a %.2fs cooldown.' % error.retry_after)
            raise error  # re-raise the error so all the errors will still show up in console
        if isinstance(error, commands.CheckFailure):
            await self.commandError(channel=ctx.message.channel,
                                    message='You don\'t have the correct permissions to use this command.')
            raise error  # re-raise the error so all the errors will still show up in console
        if isinstance(error, commands.UserInputError):
            await self.commandError(channel=ctx.message.channel,
                                    message='The arguments you provided threw and Error! Please read the !help for that command.')
            raise error  # re-raise the error so all the errors will still show up in console
        if isinstance(error, commands.TooManyArguments):
            await self.commandError(channel=ctx.message.channel,
                                    message='You provided too many arguments for that command! Please read the !help for that command.')
            raise error  # re-raise the error so all the errors will still show up in console

    async def checkChannel(self, ctx):
        """
        Channels where users are permitted to use commands
        :param ctx:
        :return:
        """
        if ctx.message.guild.id in self.testServerIds:
            return True
        self.approvedChannels = dataIO.load_json("data/server/allowed_channels.json")
        if ctx.message.channel.id in self.approvedChannels:
            return True
        else:
            message = await self.commandError(channel=ctx.message.channel,
                                              message='Please go to <#780862401297383434> to use this command!')
            await asyncio.sleep(3)
            await message.delete()
            return False
        # return True

    async def removeAllRoles(self, message: discord.Message):
        """
        Remove all level roles associate with this bot
        :param ctx:
        :return:
        """
        # logger.info(f"Removing all roles for {message.author.name}")
        # level_roles = [y[1] for y in self.auth.items("level-roles")]
        # for role_name in level_roles:
        #     role = discord.utils.get(message.guild.roles, name=role_name)
        #     if role in message.author.roles:
        #         try:
        #             await self.bot.remove_roles(message.author, role)
        #             logger.info(f"Removed {role.name} from {message.author.name}")
        #         except:
        #             logger.error(f"Error removing {role.name}")
        pass

    async def removeHigherRoles(self, message: discord.Message, higher_roles):
        """
        :param ctx: discord message object
        :param higher_roles: list if ints corresponding to roles in config file
        :return:
        """
        # users_roles = [y for y in message.author.roles]
        # higher_roles = [discord.utils.get(message.guild.roles, name=self.auth.get('level-roles', f'lvl_{level}')) for level in higher_roles]
        # _removed = 0
        # if not any(x in higher_roles for x in users_roles):
        #     logger.info("None of the higher roles are on this user, returning")
        #     return
        # for role in higher_roles:
        #     if role in message.author.roles:
        #         try:
        #             await self.bot.remove_roles(message.author, role)
        #             logger.debug(f"Role removed from {message.author}: {role.name}")
        #             _removed += 1
        #         except:
        #             logger.error(f"Couldn't remove role from user: {role.name}")
        #             pass
        # logger.success(f"Removed {_removed} roles from user")
        # return
        pass


def check_folders():
    if not os.path.exists("data/xp"):
        logger.info("Creating data/xp folder...")
        os.makedirs("data/xp")
    if not os.path.exists("data/xp"):
        logger.info("Creating data/server folder...")
        os.makedirs("data/server")


def check_files():
    if not dataIO.is_valid_json("data/server/allowed_channels.json"):
        logger.debug("Creating empty allowed_channels.json...")
        dataIO.save_json("data/server/allowed_channels.json", [])
    if not dataIO.is_valid_json("data/xp/banned_channels.json"):
        logger.debug("Creating empty banned_channels.json...")
        dataIO.save_json("data/xp/banned_channels.json", [])


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(Submission(bot))
