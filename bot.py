import sys
import glob
import importlib
from pathlib import Path
from pyrogram import idle
import logging
import logging.config

# Get logging configurations
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("imdbpy").setLevel(logging.ERROR)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("aiohttp.web").setLevel(logging.ERROR)


from pyrogram import Client, __version__
from pyrogram.raw.all import layer
#from database.ia_filterdb import Media
from database.users_chats_db import db
from info import *
from utils import temp
from typing import Union, Optional, AsyncGenerator
from pyrogram import types
from Script import script 
from datetime import date, datetime 
import pytz
from aiohttp import web
from plugins import web_server
import pyrogram.utils
import asyncio
from pyrogram import idle
from Deth.bot import DethBot
from Deth.util.keepalive import ping_server
from Deth.bot.clients import initialize_clients

ppath = "plugins/*.py"
files = glob.glob(ppath)
DethBot.start()
loop = asyncio.get_event_loop()

pyrogram.utils.MIN_CHANNEL_ID = -1002423451263

async def Deth_start():
    print('\n')
    print('Initalizing Deth Filter Bot')
    bot_info = await DethBot.get_me()
    DethBot.username = bot_info.username
    await initialize_clients()
    for name in files:
        with open(name) as a:
            patt = Path(a.name)
            plugin_name = patt.stem.replace(".py", "")
            plugins_dir = Path(f"plugins/{plugin_name}.py")
            import_path = "plugins.{}".format(plugin_name)
            spec = importlib.util.spec_from_file_location(import_path, plugins_dir)
            load = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(load)
            sys.modules["plugins." + plugin_name] = load
            print("Deth Filter Bot Imported => " + plugin_name)
    if ON_HEROKU:
        asyncio.create_task(ping_server())
    b_users, b_chats = await db.get_banned()
    temp.BANNED_USERS = b_users
    temp.BANNED_CHATS = b_chats
    me = await DethBot.get_me()
    temp.ME = me.id
    temp.U_NAME = me.username
    temp.B_NAME = me.first_name
    temp.B_LINK = me.mention
    DethBot.username = '@' + me.username
    logging.info(f"{me.first_name} with for Pyrogram v{__version__} (Layer {layer}) started on {me.username}.")
    logging.info(script.LOGO)
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    now = datetime.now(tz)
    time = now.strftime("%H:%M:%S %p")
    await DethBot.send_message(chat_id=LOG_CHANNEL, text=script.RESTART_TXT.format(me.mention, today, time))
    await DethBot.send_message(chat_id=SUPPORT_GROUP, text=f"<b>{me.mention} ʀᴇsᴛᴀʀᴛᴇᴅ 🤖</b>")
    app = web.AppRunner(await web_server())
    await app.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app, bind_address, PORT).start()
    await idle()
    for admin in ADMINS:
        await DethBot.send_message(chat_id=admin, text=f"<b>{me.mention} ʙᴏᴛ ʀᴇsᴛᴀʀᴛᴇᴅ ✅</b>")



if __name__ == '__main__':
    try:
        loop.run_until_complete(Deth_start())
    except KeyboardInterrupt:
        logging.info('Service Stopped Bye 👋')
