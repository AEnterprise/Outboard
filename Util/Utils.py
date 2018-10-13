import asyncio
import json
import os
import subprocess
from subprocess import Popen

from discord import NotFound

from Util import Logging


def fetch_from_disk(filename, alternative=None):
    try:
        with open(f"{filename}.json") as file:
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
    return f"{message[:limit-3]}..."


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
    max_chars -= len(prefix) + len(suffix)
    lines = str(input).splitlines(keepends=True)
    pages = []
    page = ""
    count = 0
    for line in lines:
        if len(page) + len(line) > max_chars or count == max_lines:
            if page == "":
                # single 2k line, split smaller
                words = line.split(" ")
                for word in words:
                    if len(page) + len(word) > max_chars:
                        pages.append(f"{prefix}{page}{suffix}")
                        page = f"{word} "
                    else:
                        page += f"{word} "
            else:
                pages.append(f"{prefix}{page}{suffix}")
                page = line
                count = 1
        else:
            page += line
        count += 1
    pages.append(f"{prefix}{page}{suffix}")
    return pages
