import glob
import json
import os
import re
import time
from configparser import *

from discord.ext import commands
from loguru import logger

# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
# from create_databases import Base, User

#initiate logger test
logger.add(f"file_{str(time.strftime('%Y%m%d-%H%M%S'))}.log", rotation="500 MB")

#Load the keys for bot
auth = ConfigParser()
auth.read('auth.ini')  # All my usernames and passwords for the api

# Loading Cogs for commands that are a python file
def load_cogs(folder):
    os.chdir(folder)
    files = []
    for file in glob.glob("*.py"):
        file = re.search('^([A-Za-z1-9]{1,})[^.py]', file).group(0)
        files.append(file)
    return files


def config():
    with open('config.json', 'r') as f:
        config = json.load(f)
        return config


bot = commands.Bot(command_prefix=auth.get('discord', 'PREFIX'))
# engine = create_engine('sqlite:///cogs/database.db')
# Base.metadata.bind = engine
# DBSession = sessionmaker(bind=engine)
# session = DBSession()
@bot.event
async def on_ready():
    """
    When bot is ready and online it prints that its online
    :return:
    """
    logger.debug("Bot is ready!")


@bot.command(pass_context=True)
@commands.has_permissions(administrator=True)
async def load(ctx, extension):
    try:
        bot.load_extension('cogs.' + extension)
        logger.debug(f'Loaded {extension}')
        await bot.say(f'Loaded {extension}')
    except Exception as error:
        logger.exception(f"Extension {extension} could not be loaded. [{error}]")

# TODO: Add @commands.has_permissions(administrator=True) back to this command
@bot.command(pass_context=True)
@commands.has_role("Hildabot Commander")
async def reload(ctx, extension):
    try:
        bot.unload_extension('cogs.' + extension)
        bot.load_extension('cogs.' + extension)
        logger.debug(f'Reloaded {extension}')
        await bot.say(f'Reloaded {extension}')
    except Exception as error:
        logger.exception(f"Extension {extension} could not be reloaded. [{error}]")

@bot.command()
@commands.has_permissions(administrator=True)
async def unload(extension):
    try:
        bot.unload_extension('cogs.' + extension)
        logger.debug(f'Unloaded {extension}')
        await bot.say(f'{extension} successfully unloaded')
    except Exception as error:
        logger.exception(f"Extension {extension} could not be unloaded. [{error}]")


if __name__ == "__main__":
    bot.remove_command('help')
    extensions = load_cogs('cogs')
    for extension in extensions:
        try:
            bot.load_extension('cogs.'+extension)
            logger.debug(f'Loaded {extension} cog.')
        except Exception as error:
            logger.exception(f"Extension {extension} could not be loaded. [{error}]")
    bot.run(auth.get('discord', 'TOKEN'))
