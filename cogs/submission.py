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
from dateutil.relativedelta import relativedelta
from discord.ext import commands
from loguru import logger
# scheduling stuff
from pytz import utc
from sqlalchemy import create_engine
from sqlalchemy import desc
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

# declaration for User class is in here
from create_databases import Base, User, Content
from .utils.dataIO import dataIO
from .utils.dataIO import fileIO


class Submission:

    def __init__(self, bot):
        self.bot = bot
        # Bind the data type to the engine and connect to our SQL database
        engine = create_engine('sqlite:///database.db')
        Base.metadata.bind = engine
        DBSession = sessionmaker(bind=engine)
        self.session = DBSession()  # session.commit() to store data, and session.rollback() to discard changes
        scheduler = AsyncIOScheduler(timezone=utc)
        scheduler.add_job(self.housekeeper, 'interval', days=1, replace_existing=True, coalesce=True,)
        scheduler.add_job(self.setGame, 'interval', seconds=10, replace_existing=True, coalesce=True,)
        scheduler.start()
        self.auth = configparser.ConfigParser()
        self.auth.read('../auth.ini')
        self.mee6leaderboardUrl = "https://mee6.xyz/api/plugins/levels/leaderboard/492572315138392064?limit=999"
        self.messageSetting = 0
        self.approvedChannels = ['495034452422950915', '538968395538759691', '492579714674720778',
                                 '492580926111481859', '492580873628286976', '492578733442465804',
                                 '495752934890536971', '493352703519490078']

    async def setGame(self):
        if self.messageSetting == 0:
            members = 0
            for server in self.bot.servers:
                for member in server.members:
                    members += 1
            self.messageSetting = 1
            await self.bot.change_presence(game=discord.Game(name=f'!help | on Hildacord with {members} members',
                                                        url='https://www.patreon.com/botboi',
                                                        type=1))

        elif self.messageSetting == 1:
            await self.bot.change_presence(game=discord.Game(name='!help | www.patreon.com/botboi',
                                                             url='https://www.patreon.com/botboi',
                                                             type=1))
            self.messageSetting = 0

    async def commandError(self, message, channel):
        embed = discord.Embed(title="Command Error!",
                              description=message,
                              color=0xff0007)
        await self.bot.send_message(channel, embed=embed)

    async def commandSuccess(self, title, desc, channel):
        embed = discord.Embed(title=title, description=desc, color=0x00df00)
        await self.bot.send_message(channel, embed=embed)

    @commands.has_role("Staff")
    @commands.command(pass_context=True)
    async def backup(self, ctx):
        if await self.checkChannel(ctx):
            content = self.session.query(Content).all()
            with open("../backup.csv", "w") as f:
                f.write("submission_id,message_id,user,date,link,score,comment\n")
                for row in content:
                    f.write(str(row.submission_id) + ',' + str(row.message_id)
                            + ',' + str(row.user) + ',' + str(row.datesubmitted) + ',' + str(row.link)
                            + ',' + str(row.score) + ',' + str(row.comment) + "\n")
            embed = discord.Embed(title="Backup Complete!", color=0x00ff00)
            await self.bot.send_message(ctx.message.channel, embed=embed)
            await self.bot.send_file(ctx.message.author, '../backup.csv')
            logger.success("Done")

    async def on_message(self, message):
        if message.content.startswith('!') == False and message.author != self.bot.user: #553858156791332864
            db_user = await self.getDBUser(message.author.id)
            if db_user != None:
                xp = int(len(message.content.split())*0.5)
                await self.giveXP(db_user, xp)
                await self.levelup(message)
            else:
                await self.register(message)

    async def on_reaction_add(self, reaction, user):
        userToUpdate = reaction.message.author.id
        logger.debug("reaction added " + user.name + " " + str(reaction.emoji))
        try:
            logger.debug("reaction added " + user.name + " " + str(reaction.emoji))
            if type(reaction.emoji) is discord.Emoji:
                logger.debug("reaction added " + user.name + " " + str(reaction.emoji))
                #<:HildaNice:554394104117723136>
                if reaction.emoji.id == '554394104117723136' and reaction.message.content.startswith("!submit"):
                    logger.debug("reaction added " + user.name + " " + str(reaction.emoji))
                    # find user in database using id
                    db_user = self.session.query(User).filter(User.id == user.id).one()
                    message_id = reaction.message.id
                    content_author = self.session.query(Content).filter(Content.message_id == message_id).one()
                    # increase adores by 1 and xp
                    db_user.adores += 1
                    db_user.currentxp += random.randint(20,25)
                    content_author.score += 1
                    # commit session
                    self.session.commit()
                else:
                    pass
        except:
            logger.error("Adding reaction broke for user " + userToUpdate)

    async def on_reaction_remove(self, reaction, user):
        userToUpdate = reaction.message.author.id
        # logger.debug("reaction added " + user.name + " " + str(reaction.emoji))
        try:
            # logger.debug("reaction added " + user.name + " " + str(reaction.emoji))
            if type(reaction.emoji) is discord.Emoji:
                # logger.debug("reaction added " + user.name + " " + str(reaction.emoji))
                if reaction.emoji.id == '554394104117723136' and reaction.message.content.startswith("!submit"):
                    logger.debug("reaction removed " + user.name + " " + str(reaction.emoji))
                    # find user in database using id
                    db_user = self.session.query(User).filter(User.id == user.id).one()
                    message_id = reaction.message.id
                    content_author = self.session.query(Content).filter(Content.message_id == message_id).one()
                    # increase adores by 1 and xp
                    db_user.adores -= 1
                    db_user.currentxp -= 20
                    content_author.score -= 1
                    # commit session
                    self.session.commit()
                else:
                    logger.error("No plz")
        except:
            logger.error("Adding reaction broke for user " + userToUpdate)

    async def getDBUser(self, userID: str):# gets the database user based on the user's ID
        db_user = None  # return none if we can't find a user
        if userID != "426541567092850703" and userID != "525814724567367682":
            try:  # try to find user in database using id
                db_user = self.session.query(User).filter(User.id == userID).one()
            except sqlalchemy.orm.exc.NoResultFound:
                logger.error(f'No user found, probably not registered {userID}')
            except sqlalchemy.orm.exc.MultipleResultsFound:
                logger.error('Multiple users found, something is really broken!')
            return db_user  # this value will be None or a valid user, make sure to check

    async def getDBUserbyUsername(self, username):  # gets the database user based on the user's ID
        db_user = None  # return none if we can't find a user
        try:  # try to find user in database using id
            db_user = self.session.query(User).filter(User.name == username).one()
        except sqlalchemy.orm.exc.NoResultFound:
            logger.error(f'No user found, probably not registered {username}')
        except sqlalchemy.orm.exc.MultipleResultsFound:
            logger.error('Multiple users found, something is really broken!')
        return db_user  # this value will be None or a valid user, make sure t

    async def linkSubmit(self, message, userToUpdate, comment):
        url_pattern = "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        url = re.search(url_pattern, message.content.lower()).group(0)
        logger.debug('link submitting for ' + str(userToUpdate.name))
        logger.debug(str(userToUpdate.name) + "'s url - " + url[1])
        await self.handleSubmit(message, userToUpdate, url, comment)

    @commands.cooldown(1,90, commands.BucketType.server)
    @commands.has_role("Staff")
    @commands.command(pass_context=True)
    async def checkall(self, ctx):
        if await self.checkChannel(ctx):
            page = requests.get(self.mee6leaderboardUrl)
            soup = BeautifulSoup(page.content, 'html.parser')
            leaderboard = soup.prettify()
            d = json.loads(leaderboard)['players']
            users_updated = 0
            for mee6_user in d:
                db_user = await self.getDBUser(mee6_user['id'])
                if (db_user == None):
                    curdate = datetime.utcnow()
                    discord_user = await self.bot.get_user_info(mee6_user['id'])
                    new_user = User(name=discord_user.name, level=mee6_user['level'],
                                    server_id=ctx.message.server.id,
                                    id=mee6_user['id'], startdate=curdate, currency=0,
                                    streak=0, expiry=curdate, submitted=False, raffle=False, promptsadded=0,
                                    totalsubmissions=0,
                                    currentxp=0, adores=0, highscore=0, decaywarning=True, levelnotification=True)
                    self.session.add(new_user)
                    self.session.commit()
                    users_updated += 1
                else:
                    db_user.level = mee6_user['level']
                    self.session.commit()
                    users_updated += 1
            embed = discord.Embed(title="Mee6 Users Updated!", description=f"{users_updated} User records were updated!",
                                  color=0x47d740)
            await self.bot.send_message(ctx.message.channel, embed=embed)

    @commands.command(pass_context=True)
    async def leaderboard(self, ctx):
        if await self.checkChannel(ctx):
            leaderboard = self.session.query(User).filter(User.server_id == ctx.message.server.id).order_by(desc(User.level)).limit(10)
            embed = discord.Embed(title="__**Leaderboard**__", thumbnail=ctx.message.server.icon, description="The top 10 users of this server!", colour=0xb2cefe)
            for user in leaderboard:
                embed.add_field(name=":black_small_square: " + user.name + f"  Level: {user.level} | XP: {user.currentxp}", value="==========", inline=False)

            await self.bot.send_message(ctx.message.channel, embed=embed)

    @commands.command(pass_context=True)
    async def submit(self, ctx):
        if await self.checkChannel(ctx):
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

    @commands.command(pass_context=True)
    async def streakwarning(self, ctx, setting=None):
        if await self.checkChannel(ctx):
            channel = ctx.message.channel.id
            server_id = ctx.message.server.id
            db_user = await self.getDBUser(ctx.message.author.id)
            if db_user != None:
                if setting == None:
                    await self.commandError(
                        "Please specify the status of your level up messages. !streakwarning [on | off]",
                        ctx.message.channel)
                    return

                elif setting.lower() == 'on':
                    db_user.decaywarning = True
                    self.session.commit()
                    await self.bot.send_message(self.bot.get_channel(channel),
                                                f"```diff\n+ Decay warning notification for {ctx.message.author} are now on!\n```")
                elif setting.lower() == 'off':
                    db_user.decaywarning = False
                    self.session.commit()
                    await self.bot.send_message(self.bot.get_channel(channel),
                                                f"```diff\n+ Decay warning notification for {ctx.message.author} are now off!\n```")

    @commands.command(pass_context=True)
    async def levelwarning(self, ctx, setting = None):
        if await self.checkChannel(ctx):
            channel = ctx.message.channel.id
            server_id = ctx.message.server.id
            db_user = await self.getDBUser(ctx.message.author.id)
            if db_user != None:
                if setting == None:
                    await self.commandError("Please specify the status of your level up messages. !levelwarning {on | off}",
                                            ctx.message.channel)
                    return

                elif setting.lower() == 'on':
                    db_user.levelnotification = True
                    self.session.commit()
                    await self.bot.send_message(self.bot.get_channel(channel), f"```diff\n+ Level up notification for {ctx.message.author} are now on!\n```")
                elif setting.lower() == 'off':
                    db_user.levelnotification = False
                    self.session.commit()
                    await self.bot.send_message(self.bot.get_channel(channel), f"```diff\n+ Level up notification for {ctx.message.author} are now off!\n```")

    @commands.command(pass_context=True)
    async def stats(self, ctx, user: discord.Member = None):
        if await self.checkChannel(ctx):
            # try to find user in database using id
            if user == None:
                db_user = await self.getDBUser(ctx.message.author.id)
                author = ctx.message.author

            else:
                db_user = await self.getDBUser(user.id)
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
                    stats_embed = discord.Embed(title=name,
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
                    stats_embed = discord.Embed(title=name,
                                                description="{}, Level: {}".format(top_role, stats['level']),
                                                color=0x33cccc)
                    pass
                stats_embed.add_field(name="Progress:", value=f"{stats['expbar']}")
                stats_embed.add_field(name="**XP**:", value=f"{stats['xp']}/{stats['next_level_required_xp']}", inline=True)
                stats_embed.add_field(name="**Current Streak**:", value="{0}".format(stats['streak']), inline=True)
                stats_embed.add_field(name="**High Score**:", value="{0}".format(stats['highscore']), inline=True)
                stats_embed.add_field(name="**Kudos**:", value=f"{self.auth.get('discord', 'KUDOS_ID')} **Given**: {stats['adores_given']} | {self.auth.get('discord', 'KUDOS_ID')} **Received**: {stats['adores_gotten']}", inline=True)
                stats_embed.add_field(name="Stats",
                                      value=f"    **Submits**: {stats['total_submissions']} | **Tokens**: {stats['coins']}",
                                      inline=False)

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
                    submit_status = ":white_check_mark: You have submitted today"
                else:
                    submit_status = ":regional_indicator_x: You have not submitted today."
                # score_card = name_card + xp_card + adores_card + stats_card
                stats_embed.add_field(name="Submit Status", value=submit_status, inline=True)
                stats_embed.set_footer(text="Streaks Expires: {0} Days, {1} Hours, {2} Minutes, {3} Seconds.".format(
                    d_days, d_hour, d_min, d_sec))

                await self.bot.send_message(ctx.message.channel, embed=stats_embed)
            else:
                await self.bot.send_message(ctx.message.channel,
                                          "```diff\n- I couldn't find your name in our database. Are you sure you're registered? If you are, contact an admin immediately.\n```")

    @commands.command(pass_context=True)
    async def timeleft(self, ctx):
        if await self.checkChannel(ctx):
            now = datetime.utcnow()
            # CST Time Zone
            end = datetime(now.year, now.month, now.day, hour=6, minute=0, second=0, microsecond=0)
            difference = end - now
            seconds_to_work = difference.seconds
            difference_hours = math.floor(seconds_to_work / 3600)
            seconds_to_work = seconds_to_work - 3600 * difference_hours
            difference_minutes = math.floor(seconds_to_work / 60)
            seconds_to_work = seconds_to_work - 60 * difference_minutes
            if difference_hours < 5:
                await self.bot.send_message(ctx.message.channel,
                                          '```diff\n- {0} hours, {1} minutes, and {2} seconds left to submit for today!\n```'.format(
                                              difference_hours, difference_minutes, seconds_to_work))
            else:
                await self.bot.send_message(ctx.message.channel,
                                          '```diff\n+ {0} hours, {1} minutes, and {2} seconds left to submit for today!\n```'.format(
                                              difference_hours, difference_minutes, seconds_to_work))

    @commands.command(pass_context=True)
    async def idea(self, ctx):
        if await self.checkChannel(ctx):
            serv = ctx.message.server
            # try to find user in database using id
            db_user = await self.getDBUser(ctx.message.author.id)

            if (db_user == None):
                await self.bot.send_message(ctx.message.channel, "```diff\n- You need to be registered to suggest prompts.\n```")
            else:
                if ctx.message.content[5:].lstrip(" ") == "":
                    await self.commandError("Your must specify a prompt suggestion for this command to work! !idea {your brilliant idea}",
                                      ctx.message.channel)
                    return
                db_user.promptsadded = newpromptscore = db_user.promptsadded + 1
                self.session.commit()
                await self.bot.send_message(ctx.message.channel, "```diff\n+ Your prompt suggestion has been recorded!\n```")
                if newpromptscore == 20:
                    for rank in serv.roles:
                        if rank.name == "Idea Machine":
                            await self.bot.add_roles(ctx.message.author, rank)
                            await self.bot.send_message(ctx.message.channel,
                                                      "```Python\n @{0} Achievement Unlocked: Idea Machine\n```".format(
                                                          ctx.message.author.name))
                        else:
                            try:
                                role = self.bot.create_role(name="Idea Machine")
                                logger.success("Role created: Idea Machine")
                                await self.bot.add_roles(ctx.message.author, rank)
                            except Exception:
                                logger.error("Could not create role: Idea Machine")
                                await self.bot.send_message(ctx.message.channel,
                                                            "```diff\n- Could not create role: Idea Machine. Please check bot permissions.\n```")

                with open('../prompts.txt', 'a+') as fp:
                    fp.write(ctx.message.content[6:] + '\n')

    async def register(self, message):
        curdate = datetime.utcnow()
        today = "{0}-{1}-{2}".format(curdate.month, curdate.day, curdate.year)
        already_registered = False
        # try to find user in database using id
        db_user = await self.getDBUser(message.author.id)

        # add a new user if there's no registered user
        if (db_user == None):
            # create new user object
            new_user = User(name=message.author.name, server_id=str(message.server.id), level=1, id=message.author.id, startdate=curdate, currency=0,
                            streak=0, expiry=curdate, submitted=False, raffle=False, promptsadded=0, totalsubmissions=0,
                            currentxp=0, adores=0, highscore=0, decaywarning=True, levelnotification=True)
            # add to session
            self.session.add(new_user)
            # # give relevant roles
            # serv = ctx.message.server
            # role = discord.utils.get(serv.roles, name="0+ Streak")
            # user = ctx.message.author
            # if role is None:
            #     await self.bot.create_role(serv, name='0+ Streak')
            #     role_new = discord.utils.get(serv.roles, name="0+ Streak")
            #     await self.bot.add_roles(user, role_new)
            # else:
            #     await self.bot.add_roles(user, role)


            # for rank in serv.roles:
            #     if rank.name == "Artists":
            #         await self.bot.add_roles(ctx.message.author, rank)
            #     else:
            #         try:
            #             rank = self.bot.create_role(name='Artists')
            #             await self.bot.add_roles(ctx.message.author, rank)
            #         except Exception:
            #             logger.error('Could not create/assign role: Artists')
            # commit session
            self.session.commit()
            logger.success(f"+ Successfully registered {message.author.name}")
        else:
            logger.error(f"# {message.author.name} is already registered!")

    @commands.command(pass_context=True)
    async def randomidea(self, ctx):
        if await self.checkChannel(ctx):
            with open("../prompts.txt", "r") as f:
                lines = f.read().split('\n')
            await self.bot.send_message(ctx.message.channel, "```diff\n{}\n```".format(random.choice(lines)))

    @commands.has_role('Staff')
    @commands.command(pass_context=True)
    async def fullreset(self, ctx, user = None):
        if await self.checkChannel(ctx):
            if user == None:
                receiver = ctx.message.author
            elif user != None and type(user) is discord.Member:
                receiver = user
            else:
                await self.bot.send_message(ctx.message.channel,
                                            "```\n!fullreset {@user} to reset a user or !fullreset to reset yourself.\n```")
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
                await self.bot.send_message(ctx.message.channel,
                                          "```Markdown\n#{0} stats have been fully reset\n```".format(receiver.name))
            except:
                await self.bot.send_message(ctx.message.channel, "```Markdown\n#Something went wrong.\n```")
                self.session.rollback()

    @commands.command(pass_context=True)
    async def kots(self, ctx):
        with open(f'data/server/cursedhilda.png', 'rb') as f:
            icon = f.read()
        await self.bot.edit_server(ctx.message.server, icon=icon)
        await self.bot.send_message(ctx.message.author, "Server icon updated ;)")

    @commands.has_role("Staff")
    @commands.command(pass_context=True)
    async def deletesubmissions(self, ctx, user : discord.Member = None):
        if await self.checkChannel(ctx):
            if user == None:
                await self.bot.send_message(ctx.message.channel, "Please specify a user.")
            else:
                db_user = await self.getDBUser(user.id)
                if db_user == None:
                    await self.bot.send_message(ctx.message.channel, "User is not registered.")
                else:
                    content = len(self.session.query(Content).filter_by(user = user.name).all())
                    if content > 0:
                        self.session.query(Content).filter_by(user = user.name).delete()
                        self.session.commit()
                        await self.bot.send_message(ctx.message.channel, f"{user.name}'s submissions have been removed from the DB")
                    else:
                        await self.bot.send_message(ctx.message.channel, f"{user.name} has no submissions to remove.")

    @commands.has_role("Staff")
    @commands.command(pass_context=True)
    async def delete(self, ctx, user: discord.Member = None):
        if await self.checkChannel(ctx):
            if user is None:
                await self.commandError(channel=ctx.message.channel, message="!delete [user] requires you to mention a discord user to delete their record in the database")
                return
            msg = await self.bot.send_message(ctx.message.channel, 'Are you sure you want to COMPLETELY erase this user?')
            await self.bot.add_reaction(msg, u"\U0001F44D")
            await self.bot.add_reaction(msg, u"\U0001F44E")
            res = await self.bot.wait_for_reaction([u"\U0001F44D", u"\U0001F44E"], user=ctx.message.author, message=msg, timeout=15)
            logger.info(res.reaction.emoji)
            if res.reaction.emoji == u"\U0001F44D":
                db_user = await self.getDBUser(user.id)
                if db_user != None:
                    try:
                        receiver = user
                        db_user = self.session.query(User).filter(User.id == str(receiver.id)).delete()
                        db_user = self.session.query(Content).filter(Content.user == str(receiver.name)).delete()
                        self.session.commit()
                        logger.success(f"User {user.name} has been deleted from the DB by {ctx.message.author.name}")
                        await self.commandSuccess(channel=ctx.message.channel,title="User Successfully Deleted",
                                                  desc="Users Stats and submissions have been removed from the Database.")
                        await self.bot.delete_message(msg)
                    except SQLAlchemyError as e:
                        logger.error(e)
                else:
                    await self.commandError("User's ID could not but found in the Database", ctx.message.channel)
            elif res.reaction.emoji == u"\U0001F44E":
                canceled = await self.bot.send_message(ctx.message.channel, "Action canceled.")
                await self.bot.delete_message(msg)

            else:
                canceled = await self.bot.send_message(ctx.message.channel, "Action canceled. [invalid reaction]")
                await self.bot.delete_message(msg)

    @commands.has_role("Staff")
    @commands.command(pass_context=True)
    async def rollback(self, ctx, messageID = None):
        if await self.checkChannel(ctx):
            submission = self.getDBSubmission(messageID)
            if submission is None:
                await self.bot.send_message(ctx.message.channel,
                                            "```diff\n- No such Submission. Make sure you are using the message ID of the submit post.\n```")
                return
            remove = self.removeDBSubmission(messageID)
            if remove is True:
                db_user = await self.getDBUserbyUsername(submission.user)
                newscore = db_user.totalsubmissions - 1
                newcurrency = db_user.currency - 10
                current_streak = db_user.streak
                new_streak = current_streak - 1
                current_xp = db_user.currentxp
                xp_gained = 20 + int(math.floor(current_streak * 5))
                current_level = db_user.level
                new_xp_total = current_xp - xp_gained
                if new_xp_total < 0: # decrease level
                    current_level = current_level - 1
                    next_level_required_xp = current_level * 10 + 50
                    new_xp_total = new_xp_total - next_level_required_xp
                    db_user.level = str(current_level)
                    db_user.currentxp = str(new_xp_total)

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
                db_user.submitted = 0
                # and push all cells to the database
                self.session.commit()
                await self.bot.send_message(ctx.message.channel,
                                      "```diff\n+ Submission has been removed from the DB.\n```")

            elif remove is False:
                await self.bot.send_message(ctx.message.channel,
                                      "```diff\n- Error Removing Submission from DB, check logs.\n```")

            else:
                await self.bot.send_message(ctx.message.channel,
                                      "```diff\n- Error Removing Submission from DB, check logs.\n```")

    async def levelup(self, message):
        db_user = await self.getDBUser(message.author.id)
        if db_user != None:
            stats = await self.getUserStats(db_user)
            xp = stats['xp']
            lvl_end = stats['next_level_required_xp']
            if xp > lvl_end:
                stats['level'] += 1
                new_xp_total = xp - stats['next_level_required_xp']
                db_user.level = str(stats['level'])
                db_user.currentxp = str(new_xp_total)
                await self.updateRole(stats['level'], message)
                self.session.commit()
                if db_user.levelnotification != False:
                    await self.commandSuccess(f'@{stats["user_name"]} Leveled Up! You are now level {str(stats["level"])}! :confetti_ball:',
                                            'To turn off this notification do !levelwarning off in any channel.',
                                            message.author)
                    return
            else:
                await self.checkLevel(message, db_user.level)

    @commands.cooldown(1,30, commands.BucketType.channel)
    @commands.command(pass_context=True)
    async def help(self, ctx, command=None):
        if command is None:
            embed = discord.Embed(title="Hildabot Help",
                                  description='Here is a list of all of the commands you can use!',
                                  color=0x90BDD4)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/503498544485892100.png")
            role_names = [role.name for role in ctx.message.author.roles]
            if 'Staff' in role_names:
                embed.add_field(name="!delete [user]",
                                value="Removes a user from the database (Staff only! VERY DANGEROUS)",
                                inline=False)
                embed.add_field(name="!fullreset", value="Sets a users stats to 0. (Staff only!)",
                                inline=False)
                embed.add_field(name="!deletesubmissions [user]",
                                value="Removes a user's submissions from the database "
                                      "(Staff only! VERY DANGEROUS)",
                                inline=False)
            embed.add_field(name="!leaderboard",
                            value="Shows you the top 10 users in in the server.",
                            inline=False)
            embed.add_field(name="!rollback [message id]",
                            value="removes a submission from the DB and rolls back the xp "
                                  "gained from it. (Staff only!)",
                            inline=False)
            embed.add_field(name="!stats", value="To see your current scorecard", inline=False)
            embed.add_field(name="!submit",
                            value="To submit content, drag and drop the file (.png, .gif, .jpg) "
                                  "into discord and add '!submit' as a comment to it.",
                            inline=False)
            embed.add_field(name="!submit [link]",
                            value="If you'd like to submit via internet link, make sure you right click"
                                  " the image and select 'copy image location' and submit that URL using"
                                  " the !submit command.",
                            inline=False)
            embed.add_field(name="!timeleft",
                            value="The !timeleft command will let you know how much longer you have "
                                  "left to submit for the day!",
                            inline=False)
            embed.add_field(name="!randomidea",
                            value="Having trouble figuring out what to create?",
                            inline=False)
            embed.add_field(name="!rollback [message id]",
                            value="removes a submission from the DB and rolls back the xp "
                                  "gained from it. (Staff only!)",
                            inline=False)
            embed.add_field(name="!stats", value="To see your current scorecard", inline=False)
            embed.add_field(name="!submit",
                            value="To submit content, drag and drop the file (.png, .gif, .jpg) "
                                  "into discord and add '!submit' as a comment to it.",
                            inline=False)
            embed.add_field(name="!submit [link]",
                            value="If you'd like to submit via internet link, make sure you right click"
                                  " the image and select 'copy image location' and submit that URL using"
                                  " the !submit command.",
                            inline=False)
            embed.add_field(name="!timeleft",
                            value="The !timeleft command will let you know how much longer you have "
                                  "left to submit for the day!",
                            inline=False)
            embed.add_field(name="!idea [idea]",
                            value="Add a random idea to the \"randomidea\" list!",
                            inline=False)
            embed.add_field(name="!levelwarning [on | off]",
                            value="To turn on or off the PM warning system about your streak use the "
                                  "command !levelwarning on or !levelwarning off.",
                            inline=False)
            embed.set_footer(text="If you have any questions or concerns, please contact a Staff "
                                  "member.")
            await self.bot.say(embed=embed)

    async def submitLinktoDB(self, user, link, message_id, comments):
        try:
            new_content = Content()
            new_content.user = user
            new_content.datesubmitted = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            new_content.link = link
            new_content.score = 0
            new_content.message_id = message_id
            new_content.comment = comments
            self.session.add(new_content)
            self.session.commit()
            logger.success("added content to db")
        except Exception as e:
            logger.error(e)

    async def normalSubmit(self, message, userToUpdate, comment):
        logger.debug('submitting for ' + str(userToUpdate.name))
        jsonstr = json.dumps(message.attachments[0])
        jsondict = json.loads(jsonstr)
        url = jsondict['url']
        logger.debug(str(userToUpdate.name) + "'s url - " + url)
        await self.handleSubmit(message, userToUpdate, url, comment)

    async def handleSubmit(self, message, userToUpdate, url, comment):
        curdate = datetime.utcnow()
        potentialstreak = curdate + timedelta(days=7)
        today = "{0}-{1}-{2}".format(curdate.month, curdate.day, curdate.year)
        streakdate = "{0}-{1}-{2}".format(potentialstreak.month, potentialstreak.day, potentialstreak.year)
        logger.debug('getting filepath to download for ' + str(userToUpdate.name))

        # try to find user in database using id
        db_user = await self.getDBUser(userToUpdate.id)

        # first find if we have  the user in our list

        if (db_user == None):
            await self.bot.send_message(message.channel,
                                      "```diff\n- I couldn't find your name in our spreadsheet. Are you sure you're registered? If you are, contact an admin immediately.\n```")
        else:
            # db_user is our member object

            # check if already submitted
            if db_user.submitted == 1:
                logger.error(str(userToUpdate.name) + ' already submitted')
                await self.bot.send_message(message.channel,
                                          "```diff\n- You seem to have submitted something today already!\n```")
            # otherwise, do the submit
            else:
                # update all the stats
                newscore = db_user.totalsubmissions + 1
                newcurrency = db_user.currency + 10
                new_streak = int(db_user.streak) + 1
                current_xp = db_user.currentxp
                xp_gained = 20 + int(math.floor(new_streak * 5))
                current_level = int(db_user.level)
                next_level_required_xp = current_level * 10 + 50
                new_xp_total = current_xp + xp_gained
                # if we levelled up, increase level
                if new_xp_total >= next_level_required_xp:
                    current_level = current_level + 1
                    # self.levelUpUser(current_level, userToUpdate)
                    new_xp_total = new_xp_total - next_level_required_xp
                    db_user.level = str(current_level)
                    db_user.currentxp = str(new_xp_total)
                    server_id = message.server.id
                    if db_user.levelnotification == True:
                        await self.commandSuccess(
                            f'@{userToUpdate.name} Leveled Up! You are now level {str(current_level)}! :confetti_ball:',
                            'To turn off this notification do !levelwarning off in any channel.',
                            userToUpdate)
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
                db_user.submitted = int(self.auth.get('discord', 'LIVE'))
                db_user.expiry = potentialstreak
                # and push all cells to the database
                self.session.commit()
                await self.submitLinktoDB(user=userToUpdate.name, link=url, message_id=str(message.id), comments=comment)
                logger.success("finishing updating " + db_user.name + "'s stats")
                await self.bot.send_message(message.channel,
                                          "```diff\n+ @{0} Submission Successful! Score updated!\n+ {1}xp gained.```".format(
                                              userToUpdate.name, xp_gained))

    async def housekeeper(self):
        curdate = datetime.utcnow()
        today = "{0}-{1}-{2}".format(curdate.month, curdate.day, curdate.year)

        # get all rows and put into memory
        members = self.session.query(User).all()
        logger.debug("Housekeeping on " + str(len(members)) + " rows on " + today)

        # reset all member's submitted status
        stmt = update(User).values(submitted=False)
        self.session.execute(stmt)
        self.session.commit()

        for curr_member in members:
            logger.debug('housekeeping member {0}'.format(curr_member.name))
            # Update in batch
            # set user in beginning if its needed to PM a user
            user = discord.utils.get(self.bot.get_all_members(), id=str(curr_member.id))
            if (user != None):
                # check for warning until streak decay begins
                days_left = (curr_member.expiry - curdate.date()).days
                if (curr_member.decaywarning == True and curr_member.streak > 0):
                    if (days_left == 3):
                        try:
                            await self.bot.send_message(user,
                                                      "You have 3 days until your streak begins to expire!\nIf you want to disable these warning messages then enter the command !streakwarning off in the #bot-channel")
                        except:
                            logger.error('couldn\'t send 3day message')
                    elif (days_left == 1):
                        try:
                            await self.bot.send_message(user,
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
                        await self.bot.send_message(user,
                                                  "Your streak has decayed by {0} points! Your streak is now {1}.\nIf you want to disable these warning messages then enter the command !streakwarning off in the #bot-channel".format(
                                                      str(pointReduce), str(curr_member.streak)))
                    except:
                        logger.error('couldn\'t  send decay message')
        # commit all changes to the sheet at once
        self.session.commit()
        logger.success("housekeeping finished")

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

    async def updateRole(self, current_level, ctx):
        levels = []
        for key in self.auth['level-roles']:
            # logger.info(key)
            level = re.search("^lvl_(\d+)$", key)
            levels.append(int(level.group(1)))
        if current_level in levels:
            logger.info("updating roles")
            role = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', f'lvl_{current_level}'))
            if role != None:
                await self.bot.add_roles(ctx.author, role)
            else:
                logger.error(f"Role {self.auth.get('level-roles', f'lvl_{current_level}')} does not exist on this server")
                return
            if levels.index(current_level) != 0:
                role_remove = levels[(levels.index(current_level) - 1)]
                role_remove = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', f'lvl_{role_remove}'))
                if role_remove != None:
                    await self.bot.remove_roles(ctx.author, role_remove)
                else:
                    logger.error(
                        f"Role to be removed does not exist on this server")
                    return

        # role_updated = False
        # if current_level == 3:
        #     role = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_3'))
        #     if role == None:
        #         logger.error("Level Role does not exist! please check your bot config and server config")
        #         return
        #     await self.bot.add_roles(ctx.author, role)
        #     role_updated = True
        # elif current_level == 15:
        #     role = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_15'))
        #     if role == None:
        #         logger.error("Level Role does not exist! please check your bot config and server config")
        #         return
        #     role_remove = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_3'))
        #     await self.bot.add_roles(ctx.author, role)
        #     await self.bot.remove_roles(ctx.author, role_remove)
        #     role_updated = True
        # elif current_level == 25:
        #     role = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_25'))
        #     if role == None:
        #         logger.error("Level Role does not exist! please check your bot config and server config")
        #         return
        #     role_remove = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_15'))
        #     await self.bot.add_roles(ctx.author, role)
        #     await self.bot.remove_roles(ctx.author, role_remove)
        #     role_updated = True
        # elif current_level == 35:
        #     role = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_35'))
        #     if role == None:
        #         logger.error("Level Role does not exist! please check your bot config and server config")
        #         return
        #     role_remove = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_25'))
        #     await self.bot.add_roles(ctx.author, role)
        #     await self.bot.remove_roles(ctx.author, role_remove)
        #     role_updated = True
        #
        # elif current_level == 50:
        #     role = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_50'))
        #     if role == None:
        #         logger.error("Level Role does not exist! please check your bot config and server config")
        #         return
        #     role_remove = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_35'))
        #     await self.bot.add_roles(ctx.author, role)
        #     await self.bot.remove_roles(ctx.author, role_remove)
        #     role_updated = True
        #
        # elif current_level == 60:
        #     role = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_60'))
        #     if role == None:
        #         logger.error("Level Role does not exist! please check your bot config and server config")
        #         return
        #     role_remove = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_50'))
        #     await self.bot.add_roles(ctx.author, role)
        #     await self.bot.remove_roles(ctx.author, role_remove)
        #     role_updated = True
        #
        # elif current_level == 69:
        #     role = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_69'))
        #     if role == None:
        #         logger.error("Level Role does not exist! please check your bot config and server config")
        #         return
        #     role_remove = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_60'))
        #     await self.bot.add_roles(ctx.author, role)
        #     await self.bot.remove_roles(ctx.author, role_remove)
        #     role_updated = True
        #
        # elif current_level == 75:
        #     role = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_75'))
        #     if role == None:
        #         logger.error("Level Role does not exist! please check your bot config and server config")
        #         return
        #     role_remove = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_69'))
        #     await self.bot.add_roles(ctx.author, role)
        #     await self.bot.remove_roles(ctx.author, role_remove)
        #     role_updated = True
        #
        # elif current_level == 90:
        #     role = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_90'))
        #     if role == None:
        #         logger.error("Level Role does not exist! please check your bot config and server config")
        #         return
        #     role_remove = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_75'))
        #     await self.bot.add_roles(ctx.author, role)
        #     await self.bot.remove_roles(ctx.author, role_remove)
        #     role_updated = True
        #
        # elif current_level == 100:
        #     role = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_100'))
        #     if role == None:
        #         logger.error("Level Role does not exist! please check your bot config and server config")
        #         return
        #     role_remove = discord.utils.get(ctx.server.roles, name=self.auth.get('level-roles', 'lvl_90'))
        #     await self.bot.add_roles(ctx.author, role)
        #     await self.bot.remove_roles(ctx.author, role_remove)
        #     role_updated = True
        #
        # else:
        #     logger.debug("Level Not in list")

        # logger.info(f"{role_updated}")

    async def getUserStats(self, db_user):
        stats = {"user_name": db_user.name,
                 "total_submissions": db_user.totalsubmissions,
                 "xp": db_user.currentxp,
                 "level": db_user.level,
                 "coins": db_user.currency,
                 "streak": db_user.streak,
                 "next_level_required_xp": (db_user.level * 10) + 50,
                 "percent": db_user.currentxp / ((db_user.level * 10) + 50),
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

    async def giveXP(self, db_user, xp):
        if (db_user == None):
            return
        else:
            await self.getUserStats(db_user)
            db_user.currentxp += int(xp)
            self.session.commit()

    async def checkLevel(self, message, current_level):
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
            role = discord.utils.get(message.server.roles, name=self.auth.get('level-roles', f'lvl_{max_level}'))
            if role in [y.name for y in message.author.roles]:
                return
            else:
                await self.bot.add_roles(message.author, role)

    async def on_command_error(self, error, ctx):
        if isinstance(error, commands.CommandOnCooldown):
            await self.commandError(channel=ctx.message.channel, message='This command is on a %.2fs cooldown.' % error.retry_after)
            raise error  # re-raise the error so all the errors will still show up in console
        if isinstance(error, commands.CheckFailure):
            await self.commandError(channel=ctx.message.channel, message='You don\'t have the correct permissions to use this command.')
            raise error  # re-raise the error so all the errors will still show up in console
        if isinstance(error, commands.UserInputError):
            await self.commandError(channel=ctx.message.channel, message='The arguments you provided threw and Error! Please read the !help for that command.')
            raise error  # re-raise the error so all the errors will still show up in console
        if isinstance(error, commands.TooManyArguments):
            await self.commandError(channel=ctx.message.channel, message='You provided too many arguments for that command! Please read the !help for that command.')
            raise error  # re-raise the error so all the errors will still show up in console
        else:
            raise error
    async def checkChannel(self, ctx):
        # TODO: Un-comment this for live.
        # if ctx.message.channel.id in self.approvedChannels:
        #     return True
        # else:
        #     await self.commandError(channel=ctx.message.channel,
        #                             message='Cannot respond within this channel')
        #     return False
        return True

def setup(bot):
    bot.add_cog(Submission(bot))