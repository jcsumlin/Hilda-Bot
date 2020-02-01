import asyncio
import os
from datetime import datetime

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands
from loguru import logger
from pytz import timezone
import re

from .utils.dataIO import dataIO, fileIO


class Birthdays:
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone='America/New_York')
        self.scheduler.add_job(self.check_birthdays, 'interval', minutes=1, replace_existing=True, coalesce=True)
        self.scheduler.start()

    async def get_config(self):
        return dataIO.load_json('data/birthday/birthdays.json')

    async def save_config(self, data):
        return dataIO.save_json('data/birthday/birthdays.json', data)

    @commands.group(pass_context=True)
    async def birthday(self, ctx):
        if ctx.invoked_subcommand is None:
            return

    @birthday.group(pass_context=True)
    async def add(self, ctx, user: discord.User, birthday):
        pattern = re.compile("^[0-9]{1,2}\/[0-9)]{1,2}\/[0-9]{4}$")
        if not pattern.match(birthday):
            await self.bot.send_message(ctx.message.channel, 'Please use MM/DD/YYYY date format!')
            return
        birthday = birthday.split('/')
        birthdays = await self.get_config()
        if int(birthday[2]) >= datetime.now().year:
            await self.bot.send_message(ctx.message.channel, "That's not a valid year silly")
            return
        if str(ctx.message.server.id) in birthdays.keys():
            birthday = datetime(year=int(birthday[2]), month=int(birthday[0]), day=int(birthday[1]))
            for birthday_user in birthdays[ctx.message.server.id]['users']:
                if birthday_user['user_id'] == user.id:
                    await self.bot.send_message(ctx.message.channel, "That User's birthday is already registered!")
                    return
            birthdays[ctx.message.server.id]['users'].append({'user_id': user.id, 'birthday': str(birthday), 'COMPLETE': False})
            await self.save_config(birthdays)
            await self.bot.send_message(ctx.message.channel,"Done!")
        else:
            await self.bot.send_message(ctx.message.channel,"Birthdays not setup!")

    @birthday.group(pass_context=True)
    @commands.has_permissions(administrator=True)
    async def role(self, ctx, role: discord.Role):
        birthdays = await self.get_config()
        logger.info(role)
        birthdays[ctx.message.server.id]['role_id'] = role.id
        await self.save_config(birthdays)
        await self.bot.send_message(ctx.message.channel, "Birthday Role Set!")

    @birthday.group(pass_context=True)
    async def edit(self, ctx, birthday):
        pattern = re.compile("^[0-9]{1,2}\/[0-9)]{1,2}\/[0-9]{4}$")
        if not pattern.match(birthday):
            await self.bot.send_message(ctx.message.channel, 'Please use MM/DD/YYYY date format!')
            return
        birthday = birthday.split('/')
        birthdays = await self.get_config()
        if int(birthday[2]) >= datetime.now().year:
            await self.bot.send_message(ctx.message.channel, "That's not a valid year silly")
            return
        if str(ctx.message.server.id) in birthdays.keys():
            birthday = datetime(year=int(birthday[2]), month=int(birthday[0]), day=int(birthday[1]))
            for birthday_user in birthdays[ctx.message.server.id]['users']:
                if birthday_user['user_id'] == ctx.message.author.id:
                    birthday_user['birthday'] = str(birthday)
                    await self.save_config(birthdays)
                    await self.bot.send_message(ctx.message.channel, "Your birthday has been updated!")
                    return
            await self.bot.send_message(ctx.message.channel, "Your "
                                                             "birthday has not been registered"
                                                             " before please add it using"
                                                             " !birthday add @your_username MM/DD/YYYY!")
        else:
            await self.bot.send_message(ctx.message.channel, "Birthdays not setup!")

    @birthday.group(pass_context=True)
    async def list(self, ctx):
        birthdays = await self.get_config()
        users = birthdays[ctx.message.server.id]['users']
        embed = discord.Embed(title=f"{ctx.message.server.name}'s Birthday list for this month :birthday:")
        for user in users:
            birthday = datetime.strptime(user['birthday'], "%Y-%m-%d 00:00:00")
            now = datetime.now()
            if birthday.month == now.month:
                user_name = discord.utils.get(ctx.message.server.members, id=user['user_id'])
                embed.add_field(name=user_name.name, value=birthday.strftime('%m/%d/%Y'))
        await self.bot.send_message(ctx.message.channel, embed=embed)

    @birthday.group(pass_context=True)
    @commands.has_permissions(administrator=True)
    async def channel(self, ctx, channel):
        birthdays = await self.get_config()
        channel_id = channel.replace("#", "").replace("<", "").replace(">", "")
        if ctx.message.server.id not in birthdays.keys():
            birthdays[ctx.message.server.id] = {'channel': channel_id, 'users': []}
        else:
            birthdays[ctx.message.server.id]['channel'] = channel_id

        await self.save_config(birthdays)
        return await self.bot.send_message(ctx.message.channel, "Birthday Channel Set! :birthday:")

    @birthday.group(pass_context=True)
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx):
        birthdays = await self.get_config()
        if ctx.message.server.id in birthdays.keys():
            birthdays[ctx.message.server.id]['channel'] = ""
            await self.save_config(birthdays)
            return await self.bot.send_message(ctx.message.channel, ":x: Birthday Messages Disabled!")
        else:
            return await self.bot.send_message(ctx.message.channel, ":interrobang: Birthday Message Channel Not Set For This Server!")

    async def check_birthdays(self):
        await self.bot.wait_until_ready()
        birthdays = await self.get_config()
        for key, value in birthdays.items():
            if len(value['users']) == 0:
                continue
            for user in value['users']:
                birthday = datetime.strptime(user['birthday'], "%Y-%m-%d 00:00:00")
                eastern = timezone('US/Eastern')
                now = datetime.now(eastern)
                channel = self.bot.get_channel(value['channel'])
                if channel is None or channel.is_private:
                    continue
                birthday_role = None
                if 'role_id' in value:
                    birthday_role = discord.utils.find(lambda r: r.id == value['role_id'],
                                                       channel.server.roles)
                member = discord.utils.find(lambda m: m.id == user['user_id'], channel.server.members)
                if member is None:
                    continue
                if birthday.month != now.month or birthday.day != now.day and user['COMPLETE']:
                    user['COMPLETE'] = False
                    if birthday_role:
                        try:
                            await self.bot.remove_roles(member, birthday_role)
                        except discord.Forbidden:
                            logger.error("Does Not have permissions to add roles to users!")
                        except Exception:
                            logger.error("Error removing role from user" + member.name)
                    await self.save_config(birthdays)
                if birthday.month == now.month and birthday.day == now.day and not user['COMPLETE']:
                    if birthday_role:
                        try:
                            await self.bot.add_roles(member, birthday_role)
                        except discord.Forbidden:
                            logger.error("Does Not have permissions to add roles to users!")
                    years = now.year - birthday.year
                    if 4 <= years <= 20 or 24 <= years <= 30:
                        suffix = "th"
                    else:
                        suffix = ["st", "nd", "rd"][years % 10 - 1]

                    await self.bot.send_message(channel, f"Hey <@{user['user_id']}>! I just wanted to wish you the happiest of birthdays on your {years}{suffix} birthday! :birthday: :heart:")
                    user['COMPLETE'] = True
                    await self.save_config(birthdays)


def check_folders():
    if not os.path.exists("data/birthday"):
        logger.info("Creating data/birthday folder...")
        os.makedirs("data/birthday")


def check_files():
    f = "data/birthday/birthdays.json"
    if not fileIO(f, "check"):
        logger.info("Creating empty birthdays.json...")
        fileIO(f, "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Birthdays(bot)
    bot.add_cog(n)
