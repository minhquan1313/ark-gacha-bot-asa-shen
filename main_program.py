import time
import discord
from discord.ext import commands
from typing import Callable
import asyncio
import pyautogui
import settings
import os
import win32gui
import win32con

intents = discord.Intents.default()
pyautogui.FAILSAFE = False
bot = commands.Bot(command_prefix=settings.command_prefix, intents=intents)


async def load_cogs():
    for filename in os.listdir("./source/discord_commands"):
        print(filename)
        if filename.endswith(".py"):
            await bot.load_extension(f"source.discord_commands.{filename[:-3]}")


focus_window_task = None


def focus_window(window_title="ArkAscended"):
    global focus_window_task

    if focus_window_task and not focus_window_task.done():
        return

    async def callback():
        while True:
            try:
                hwnd = win32gui.FindWindow(None, window_title)
                if hwnd:
                    if win32gui.GetForegroundWindow() != hwnd:
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)

                    await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Error focusing window: {e}")
            await asyncio.sleep(5)

    focus_window_task = asyncio.create_task(callback())


bot_started_once = False


@bot.event
async def on_ready():
    global bot_started_once
    await bot.tree.sync()

    logchn = bot.get_channel(int(settings.log_channel_gacha))
    if logchn:
        await logchn.send(f"bot ready to start")
        if not bot_started_once:
            bot_started_once = True

            cog = bot.get_cog("discord_commands")
            if cog:
                time.sleep(3)
                bot.loop.create_task(cog.start_bot_core(wait=0))
    print(f"logged in as {bot.user}")
    focus_window("ArkAscended")


api_key = settings.discord_api_key

if __name__ == "__main__":
    try:
        asyncio.run(load_cogs())
        bot.run(api_key)

    except Exception as e:
        print(f"ERROR:{e}")
        print("you need to have a valid discord API key for the bot to run")
        print(
            "please follow the instructions in the discord server to get your api key"
        )
        input(f"")
        exit()
