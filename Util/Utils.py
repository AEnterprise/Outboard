import asyncio
import json
import os
import subprocess
from subprocess import Popen

import discord

from Util import Logging


def fetch_from_disk(filename, extension=".json", alternative=None):
    try:
        with open(f"{filename}{extension}") as file:
            return json.load(file)
    except FileNotFoundError:
        if alternative is not None:
            fetch_from_disk(alternative)
        return dict()


def save_to_disk(filename, dict):
    with open(f"{filename}.json", "w") as file:
        json.dump(dict, file, indent=4, skipkeys=True, sort_keys=True)


def trim_message(message, limit):
    if len(message) < limit - 3:
        return message
    return f"{message[:limit - 3]}..."


async def clean_exit(bot, trigger):
    # TODO: maybe schedule a sigkill as backup option?
    await Logging.bot_log(f"Shutdown triggered by {trigger}.")
    await bot.logout()
    await bot.close()


async def execute(command):
    p = Popen(command, cwd=os.getcwd(), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while p.poll() is None:
        await asyncio.sleep(1)
    out, error = p.communicate()
    return p.returncode, out, error


def clean_user(user):
    return f"\u200b{user.name}\u200b#{user.discriminator}"


def paginate(input, max_lines=20, max_chars=1900, prefix="", suffix=""):
    max_chars -= len(prefix.format(page=100, pages=100)) + len(suffix.format(page=100, pages=100))
    lines = str(input).splitlines(keepends=True)
    pages = list()
    page = ""
    count = 0
    for line in lines:
        if len(page) + len(line) > max_chars or count == max_lines:
            if page == "":
                # single 2k line, split smaller
                words = line.split(" ")
                for word in words:
                    if len(page) + len(word) > max_chars:
                        pages.append(page)
                        page = f"{word} "
                    else:
                        page += f"{word} "
            else:
                pages.append(page)
                page = line
                count = 1
        else:
            page += line
        count += 1
    pages.append(page)
    page_count = 1
    total_pages = len(pages)
    real_pages = list()
    for page in pages:
        real_pages.append(f"{prefix.format(page=page_count, pages=total_pages)}{page}{suffix.format(page=page_count, pages=total_pages)}")
    return real_pages


def pad(text, length, char=' '):
    return f"{text}{char * (length - len(text))}"


async def add_reactions(message, info):
    embed = discord.Embed(description="\n\n".join(f"{k}: {v.__doc__}" for k, v in info.items()))
    for k in info:
        await message.add_reaction(k)
    await message.edit(content=message.content, embed=embed)


def clean(text):
    text = str(text)

    for c in ("\\", "`", "*", "_", "~", "<"):
        text = text.replace(c, f"\{c}\u200b")

    # make sure we don't have funny guys/roles named "everyone" messing it all up
    text = text.replace("@", "@\u200b")
    return text


async def get_username(bot, uid):
    user = bot.get_user(uid)
    if user is None:
        user = await bot.get_user_info(uid)
    return clean(user)
