import asyncio
import os

import discord
from discord.ext import commands
from loguru import logger

# declaration for User class is in here
from .utils.dataIO import dataIO
from .utils.dataIO import fileIO


class ServerStats:

    def __init__(self, bot):
        self.bot = bot
        self.serverStats = fileIO("data/server/stats.json", "load")

    async def on_member_join(self, member):
        serverInfoMessage = self.getServerInfoMessage(member=member)
        embed = self.newServerInfo(member=member)
        channel = self.bot.get_channel(list(serverInfoMessage.keys())[0])
        message = await self.bot.get_message(channel, list(serverInfoMessage.values())[0])
        await self.bot.edit_message(message=message, embed=embed)

    async def on_member_remove(self, member):
        serverInfoMessage = self.getServerInfoMessage(member=member)
        embed = self.newServerInfo(member=member)
        channel = self.bot.get_channel(list(serverInfoMessage.keys())[0])
        message = await self.bot.get_message(channel, list(serverInfoMessage.values())[0])
        await self.bot.edit_message(message=message, embed=embed)

    async def on_channel_delete(self, channel):
        serverInfoMessage = self.getServerInfoMessage(member=channel)
        embed = self.newServerInfo(member=channel)
        si_channel = self.bot.get_channel(list(serverInfoMessage.keys())[0])
        message = await self.bot.get_message(si_channel, list(serverInfoMessage.values())[0])
        await self.bot.edit_message(message=message, embed=embed)

    async def on_channel_create(self, channel):
        serverInfoMessage = self.getServerInfoMessage(member=channel)
        embed = self.newServerInfo(member=channel)
        si_channel = self.bot.get_channel(list(serverInfoMessage.keys())[0])
        message = await self.bot.get_message(si_channel, list(serverInfoMessage.values())[0])
        await self.bot.edit_message(message=message, embed=embed)

    async def on_server_role_create(self, role):
        serverInfoMessage = self.getServerInfoMessage(member=role)
        embed = self.newServerInfo(member=role)
        si_channel = self.bot.get_channel(list(serverInfoMessage.keys())[0])
        message = await self.bot.get_message(si_channel, list(serverInfoMessage.values())[0])
        await self.bot.edit_message(message=message, embed=embed)

    async def on_server_role_delete(self, role):
        serverInfoMessage = self.getServerInfoMessage(member=role)
        embed = self.newServerInfo(member=role)
        si_channel = self.bot.get_channel(list(serverInfoMessage.keys())[0])
        message = await self.bot.get_message(si_channel, list(serverInfoMessage.values())[0])
        await self.bot.edit_message(message=message, embed=embed)

    async def on_server_role_update(self, before, after):
        serverInfoMessage = self.getServerInfoMessage(member=before[0])
        embed = self.newServerInfo(member=before[0])
        si_channel = self.bot.get_channel(list(serverInfoMessage.keys())[0])
        message = await self.bot.get_message(si_channel, list(serverInfoMessage.values())[0])
        await self.bot.edit_message(message=message, embed=embed)

    async def on_server_emojis_update(self, before, after):
        serverInfoMessage = self.getServerInfoMessage(member=before[0])
        embed = self.newServerInfo(member=before[0])
        si_channel = self.bot.get_channel(list(serverInfoMessage.keys())[0])
        message = await self.bot.get_message(si_channel, list(serverInfoMessage.values())[0])
        await self.bot.edit_message(message=message, embed=embed)

    async def on_server_update(self, before, after):
        serverInfoMessage = self.getServerInfoMessage(server=after)
        embed = self.newServerInfo(serverObject=after)
        si_channel = self.bot.get_channel(list(serverInfoMessage.keys())[0])
        message = await self.bot.get_message(si_channel, list(serverInfoMessage.values())[0])
        await self.bot.edit_message(message=message, embed=embed)

    def getServerInfoMessage(self, member=None, server=None):
        if server is None:
            return dataIO.load_json('data/server/stats.json')[member.server.id]
        else:
            return dataIO.load_json('data/server/stats.json')[server.id]

    def newServerInfo(self, member=None, serverObject=None):
        if serverObject is None:
            server = member.server
        else:
            server = serverObject

        bots = 0
        online = 0
        for i in server.members:
            if str(i.status) == 'online' or str(i.status) == 'idle' or str(i.status) == 'dnd':
                online += 1
            if i.bot:
                bots +=1
        all_users = []
        for user in server.members:
            all_users.append('{}#{}'.format(user.name, user.discriminator))

        channel_count = 0
        for channel in server.channels:
            if channel.type == discord.ChannelType.text:
                channel_count += 1


        role_count = len(server.roles)
        # server_roles = ''
        # for role in server.roles:
        #     server_roles += role.name + ', '
        # server_roles = server_roles[:-2]
        emoji_count = len(server.emojis)
        server_owner = (str(server.owner)).replace('_', '\_').replace('*', '\*').replace('~', '\~').replace('`', '\`')


        em = discord.Embed(color=0xea7938)
        em.add_field(name='Name', value=server.name)
        em.add_field(name='Server Invite Link', value="https://discord.gg/hilda")
        em.add_field(name='Owner', value=server_owner, inline=False)
        em.add_field(name='Members', value=server.member_count)
        em.add_field(name='Bots', value=bots)
        em.add_field(name='Currently Online', value=online)
        em.add_field(name='Text Channels', value=str(channel_count))
        em.add_field(name='Region', value=server.region)
        em.add_field(name='Verification Level', value=str(server.verification_level))
        em.add_field(name='Highest role', value=server.role_hierarchy[0])
        em.add_field(name='Number of roles', value=str(role_count))
        em.add_field(name='Number of emotes', value=str(emoji_count))
        em.add_field(name='Created At',
                     value=server.created_at.__format__('%A, %d. %B %Y @ %H:%M:%S'))
        # em.add_field(name="Role List", value=server_roles, inline=True)
        em.set_thumbnail(url=server.icon_url)
        em.set_author(name='Server Info', icon_url='https://i.imgur.com/RHagTDg.png')
        em.set_footer(text='Server ID: %s' % server.id)
        return em

    async def setserverinfomessage(self, message):
        save = {message.server.id: {message.channel.id: message.id}}
        dataIO.save_json('data/server/stats.json', save)
        message_reply = await self.bot.send_message(message.channel, "Server info message set! :white_check_mark:")
        await asyncio.sleep(3)
        await self.bot.delete_message(message_reply)

    @commands.has_role("Staff")
    @commands.command(aliases=['server', 'sinfo', 'si'], pass_context=True)
    async def serverinfo(self, ctx):
        """Various info about the server. !help server for more info."""
        server = ctx.message.server
        bots = 0
        online = 0
        for i in server.members:
            if str(i.status) == 'online' or str(i.status) == 'idle' or str(i.status) == 'dnd':
                online += 1
            if i.bot:
                bots +=1

        all_users = []
        for user in server.members:
            all_users.append('{}#{}'.format(user.name, user.discriminator))
        all_users.sort()
        all = '\n'.join(all_users)

        channel_count = 0
        for channel in server.channels:
            if channel.type == discord.ChannelType.text:
                channel_count += 1

        role_count = len(server.roles)
        emoji_count = len(server.emojis)
        server_owner = (str(server.owner)).replace('_', '\_').replace('*', '\*').replace('~', '\~').replace('`', '\`')

        em = discord.Embed(color=0xea7938)
        em.add_field(name='Name', value=server.name)
        em.add_field(name='Server Invite Link', value="https://discord.gg/hilda")
        em.add_field(name='Owner', value=server_owner, inline=False)
        em.add_field(name='Members', value=server.member_count)
        em.add_field(name='Bots', value=bots)
        em.add_field(name='Currently Online', value=online)
        em.add_field(name='Text Channels', value=str(channel_count))
        em.add_field(name='Region', value=server.region)
        em.add_field(name='Verification Level', value=str(server.verification_level))
        em.add_field(name='Highest role', value=server.role_hierarchy[0])
        em.add_field(name='Number of roles', value=str(role_count))
        em.add_field(name='Number of emotes', value=str(emoji_count))
        em.add_field(name='Created At',
                     value=server.created_at.__format__('%A, %d. %B %Y @ %H:%M:%S'))
        em.set_thumbnail(url="https://images-ext-1.discordapp.net/external/ZGncUvNEnhvPPPwqpaMfqAOemiX7-CSlSOwbU1zhrPY/%3Fsize%3D1024/https/cdn.discordapp.com/icons/492572315138392064/a_2443b46341602635d0caecb9c321bb8d.gif")
        em.set_author(name='Server Info')
        em.set_footer(text='Server ID: %s' % server.id)
        message = await self.bot.send_message(ctx.message.channel, embed=em)
        await self.setserverinfomessage(message)

def check_folders():
    if not os.path.exists("data/server"):
        logger.info("Creating data/server folder...")
        os.makedirs("data/server")

def check_files():
    f = "data/server/stats.json"
    if not fileIO(f, "check"):
        logger.info("Creating empty stats.json...")
        fileIO(f, "save", [])

def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(ServerStats(bot))
