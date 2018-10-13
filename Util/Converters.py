import re

from discord.ext import commands
from discord.ext.commands import UserConverter

from Util import Utils

ID_MATCHER = re.compile("<@!?([0-9]+)>")
EMOJI_MATCHER = re.compile('<a*:([^:]+):(?:[0-9]+)>')


class PotentialID(commands.Converter):
    async def convert(self, ctx, argument):
        match = ID_MATCHER.match(argument)
        if match is not None:
            argument = match.group(1)
        try:
            argument = int(argument)
        except ValueError:
            raise commands.BadArgument("Not a potential userid")
        else:
            return argument


class Reason(commands.Converter):
    async def convert(self, ctx, argument):
        for match in EMOJI_MATCHER.finditer(argument):
            argument = argument.replace(match.group(0), f":{match.group(1)}:")
        return argument