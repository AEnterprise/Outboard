import datetime
import sys
import time
import traceback

import discord
from discord.ext import commands

from Util import Logging, Configuration, Utils

# Initialize logging
Logging.initialize()
Logging.info("Outboard initializing")

bot = commands.Bot(command_prefix="!", case_insensitive=True)
STARTED = False


@bot.event
async def on_ready():
    global STARTED
    if not STARTED:
        await Logging.onReady(bot, Configuration.get_master_var("BOT_LOG_CHANNEL"))
        await Configuration.on_ready(bot)
        
        for e in ["Maintenance", "Moderation", "BadNames"]:
            try:
                bot.load_extension("Cogs." + e)
            except Exception as ex:
                Logging.error(f"Failed to load cog {e}")
                await handle_exception(f"Loading cog {e}", ex)
        Logging.info("Cogs loaded")
        await Logging.bot_log("Outboard engine running at full speed!")
        STARTED = True
            


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return
    ctx: commands.Context = await bot.get_context(message)
    if ctx.valid and ctx.command is not None:
        if message.author.guild_permissions.ban_members:
            await bot.invoke(ctx)


@bot.event
async def on_guild_join(guild: discord.Guild):
    Logging.info(f"A new guild came up: {guild.name} ({guild.id}).")
    Configuration.load_config(guild.id)


@bot.event
async def on_guild_remove(guild: discord.Guild):
    await Logging.info(f"i was removed from a guild: {guild.name} ({guild.id}).")


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command cannot be used in private messages.")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send(error)
    elif isinstance(error, commands.MissingRequiredArgument):
        param = list(ctx.command.params.values())[min(len(ctx.args) + len(ctx.kwargs), len(ctx.command.params))]
        await ctx.send(
            f"🚫 You are missing a required command argument: `{param.name}`\n🔧Command usage: `{ctx.prefix.replace(ctx.me.mention, f'@{ctx.me.name}') + ctx.command.signature}`")
    elif isinstance(error, commands.BadArgument):
        param = list(ctx.command.params.values())[min(len(ctx.args) + len(ctx.kwargs), len(ctx.command.params))]
        await ctx.send(
            f"🚫 Failed to parse the ``{param.name}`` param: ``{error}``\n🔧 Command usage: `{ctx.prefix.replace(ctx.me.mention, f'@{ctx.me.name}') + ctx.command.signature}`")
    elif isinstance(error, commands.CommandNotFound):
        return

    else:
        await handle_exception("Command execution failed", error.original, ctx=ctx)
        # notify caller
        await ctx.send(":rotating_light: Something went wrong while executing that command :rotating_light:")


@bot.event
async def on_error(event, *args, **kwargs):
    t, exception, info = sys.exc_info()
    await handle_exception("Event handler failure", exception, event, None, None, *args, **kwargs)


def extract_info(o):
    info = ""
    if hasattr(o, "__dict__"):
        info += str(o.__dict__)
    elif hasattr(o, "__slots__"):
        items = dict()
        for slot in o.__slots__:
            try:
                items[slot] = getattr(o, slot)
            except AttributeError:
                pass
        info += str(items)
    else:
        info += str(o) + " "
    return info


async def handle_exception(exception_type, exception, event=None, message=None, ctx=None, *args, **kwargs):
    embed = discord.Embed(colour=discord.Colour(0xff0000),
                          timestamp=datetime.datetime.utcfromtimestamp(time.time()))

    # something went wrong and it might have been in on_command_error, make sure we log to the log file first
    lines = [
        "\n===========================================EXCEPTION CAUGHT, DUMPING ALL AVAILABLE INFO===========================================",
        f"Type: {exception_type}"
    ]

    arg_info = ""
    for arg in list(args):
        arg_info += extract_info(arg) + "\n"
    if arg_info == "":
        arg_info = "No arguments"

    kwarg_info = ""
    for name, arg in kwargs.items():
        kwarg_info += "{}: {}\n".format(name, extract_info(arg))
    if kwarg_info == "":
        kwarg_info = "No keyword arguments"

    lines.append("======================Exception======================")
    lines.append(f"{str(exception)} ({type(exception)})")

    lines.append("======================ARG INFO======================")
    lines.append(arg_info)

    lines.append("======================KWARG INFO======================")
    lines.append(kwarg_info)

    lines.append("======================STACKTRACE======================")
    tb = "".join(traceback.format_tb(exception.__traceback__))
    lines.append(tb)

    if message is None and event is not None and hasattr(event, "message"):
        message = event.message

    if message is None and ctx is not None:
        message = ctx.message

    if message is not None and hasattr(message, "content"):
        lines.append("======================ORIGINAL MESSAGE======================")
        lines.append(message.content)
        if message.content is None or message.content == "":
            content = "<no content>"
        else:
            content = message.content
        embed.add_field(name="Original message", value=content, inline=False)

        lines.append("======================ORIGINAL MESSAGE (DETAILED)======================")
        lines.append(extract_info(message))

    if event is not None:
        lines.append("======================EVENT NAME======================")
        lines.append(event)
        embed.add_field(name="Event", value=event)

    if ctx is not None:
        lines.append("======================COMMAND INFO======================")

        lines.append(f"Command: {ctx.command}")
        embed.add_field(name="Command", value=ctx.command)

        channel_name = 'Private Message' if isinstance(ctx.channel,
                                                       discord.abc.PrivateChannel) else f"{ctx.channel.name} (`{ctx.channel.id}`)"
        lines.append(f"Channel: {channel_name}")
        embed.add_field(name="Channel", value=channel_name, inline=False)

        sender = f"{ctx.author.name}#{ctx.author.discriminator} (`{ctx.author.id}`)"
        lines.append(f"Sender: {sender}")
        embed.add_field(name="Sender", value=sender, inline=False)

    lines.append(
        "===========================================DATA DUMP COMPLETE===========================================")
    Logging.error("\n".join(lines))

    # nice embed for info on discord

    embed.set_author(name=exception_type)
    embed.add_field(name="Exception", value=f"{str(exception)} (`{type(exception)}`)", inline=False)
    parts = Utils.paginate(tb, max_chars=1024)
    num = 1
    for part in parts:
        embed.add_field(name=f"Traceback {num}/{len(parts)}", value=part)
        num += 1

    # try logging to botlog, wrapped in an try catch as there is no higher lvl catching to prevent taking down the bot (and if we ended here it might have even been due to trying to log to botlog
    try:
        await Logging.bot_log(embed=embed)
    except Exception as ex:
        Logging.error(
            f"Failed to log to botlog, either Discord broke or something is seriously wrong!\n{ex}")
        Logging.error(traceback.format_exc())


token = Configuration.get_master_var("TOKEN")
Logging.info("Ready to go, spinning up the engine")
bot.run(token)
Logging.info("Outboard shutdown complete")
