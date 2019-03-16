import asyncio
import re
from concurrent import futures

import discord
from discord.ext import commands

from Util import Configuration, Utils


class BadNames(commands.Cog):

    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.detectors = dict()
        self.name_messages = dict()
        self.handled = set()
        self.actions = {
            "🚪": self.ban,
            "👢": self.kick,
            "🗑": self.clean_nick,
            "📝": self.rename
        }

        for guild in bot.guilds:
            self.assemble_detector(guild)

    def assemble_detector(self, guild):
        bad_names = Configuration.get_var(guild.id, "BAD_NAMES")
        if len(bad_names) > 0:
            capture = "|".join(bad_names)
            self.detectors[guild.id] = re.compile(f"({capture})", flags=re.IGNORECASE)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if after.id in self.handled:
            self.handled.remove(after.id)
            return
        if before.nick != after.nick:
            await self.check_name(after)
        elif before.name != after.name:
            for guild in self.bot.guilds:
                member = guild.get_member(after.id)
                if member is not None:
                    await self.check_name(member)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # delay checking the name by 2 seconds to allow the raid alarm to engage first in big, fast raids
        await asyncio.sleep(2)
        # we are under raid, don't check so we don't spam the crap out of the mods channel
        if member.guild.id in self.bot.get_cog("Moderation").under_raid:
            return
        await self.check_name(member)
    
    
    async def check_name(self, member):
        name_matches = self.get_matches_pretty(member.guild.id, member.name)
        if member.nick is not None:
            nick_matches = self.get_matches_pretty(member.guild.id, member.nick)
        message = ""
        if len(name_matches) > 0:
            message = f"Spotted {name_matches[0]}#{member.discriminator} (``{member.id}``) with a bad username"
            if member.nick is not None:
                if len(nick_matches) > 0:
                    message += f" AND a bad nickname ({nick_matches[0]})"
                else:
                    message += f" (current nickname is {member.nick})"
            if len(name_matches) >= 2 or (member.nick is not None and len(nick_matches) >= 2):
                if member.nick is not None:
                    name_matches.extend(nick_matches)
                out = '\n'.join(name_matches)
                message += f"\nAll matches: \n{out}"
            message += "\nWhat do you want me to do?"

        elif member.nick is not None and len(nick_matches) > 0:
            message = f"Spotted {str(member)} (``{member.id}``) with a bad nickname ({nick_matches[0]})"
            if len(nick_matches) >= 2:
                out = '\n'.join(nick_matches)
                message += f"\nAll matches: {out}"
            message += "\nWhat do you want me to do?"
        if message == "":
            return
        channel = self.bot.get_channel(Configuration.get_var(member.guild.id, "ACTION_CHANNEL"))
        if channel is not None:
            # make sure we don't accidentally ping someone
            message = message.replace("@", "@\u200b")
            message = await channel.send(message)
            self.name_messages[message.id] = member.id
            await Utils.add_reactions(message, self.actions)

            # remove the oldest if we have too many
            if len(self.name_messages) > 50:
                del self.name_messages[sorted(self.name_messages.keys())[0]]

    def get_matches(self, guild_id, name):
        return self.detectors[guild_id].findall(name) if guild_id in self.detectors else []

    def get_matches_pretty(self, guild_id, name):
        return [Utils.clean(name).replace(match, f"**{match}**") for match in self.get_matches(guild_id, name)]

    @commands.group()
    async def blacklist(self, ctx):
        """Base command for managing the name blacklist"""
        if ctx.command == self.blacklist and ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command("help"), "blacklist")

    @blacklist.command("add")
    async def blacklist_add(self, ctx, *, entry: str):
        """Add a new entry to the list"""
        guild_id = ctx.guild.id
        existing_matches = self.get_matches_pretty(guild_id, entry)
        if len(existing_matches) > 0:
            out = '\n'.join(existing_matches)
            await ctx.send(f"This name is already covered with existing entries: \n{out}")
        else:
            blacklist = Configuration.get_var(guild_id, "BAD_NAMES")
            blacklist.append(entry)
            Configuration.save(guild_id)
            self.assemble_detector(ctx.guild)
            await ctx.send(f"``{entry}`` has been added to the blacklist")

    @blacklist.command("remove")
    async def blacklist_remove(self, ctx, *, entry: str):
        """Removes an entry from the list"""
        guild_id = ctx.guild.id
        blacklist = Configuration.get_var(guild_id, "BAD_NAMES")
        if entry in blacklist:
            blacklist.remove(entry)
            Configuration.save(guild_id)
            self.assemble_detector(ctx.guild)
            await ctx.send(f"``{entry}`` has been removed from the blacklist")
        else:
            # check if it's matched under something else
            matches = self.get_matches_pretty(guild_id, entry)
            if len(matches) > 0:
                out = '\n'.join(matches)
                await ctx.send(f"``{entry}`` is not on the blacklist by itself, but parts of it are:\n{out}")
            else:
                await ctx.send(f"``{entry}`` is not on the blacklist, nor does it contain anything that is on the list")

    @blacklist.command("check")
    async def blacklist_check(self, ctx, *, entry: str):
        """Checks a string to see if it matches anything on the blacklist or not"""
        guild_id = ctx.guild.id
        matches = self.get_matches_pretty(guild_id, entry)
        if len(matches) > 0:
            out = '\n'.join(matches)
            await ctx.send(f"Yup, that is blacklisted:\n{out}")
        else:
            await ctx.send(f"``{entry}`` is not blacklisted")

    async def ban(self, channel, user, message_id, mod):
        """Ban the user"""
        name = await Utils.get_username(self.bot, user)
        try:
            await channel.guild.ban(discord.Object(user), reason=f"Inaproprate name, received ban order from {mod}")
        except discord.HTTPException as ex:
            await channel.send(f"Failed to {name} (``{user}``): {ex.text}")
        else:
            await channel.send(f"Banned {name} (``{user}``) as requested")
            del self.name_messages[message_id]

    async def kick(self, channel, user, message_id, mod):
        """Kick the user"""
        name = await Utils.get_username(self.bot, user)
        try:
            await channel.guild.kick(discord.Object(user), reason=f"Inaproprate name, received kick order from {mod}")
        except discord.HTTPException as ex:
            await channel.send(f"Failed to kick {name} (``{user}``): {ex.text}")
        else:
            await channel.send(f"Kicked user {name} (``{user}``) as requested")
            del self.name_messages[message_id]

    async def clean_nick(self, channel, user, message_id, mod):
        """Remove nickname"""
        name = await Utils.get_username(self.bot, user)
        member = channel.guild.get_member(user)
        if member is None:
            await channel.send(f"{name} (``{user}``) is no longer on the server")
        else:
            self.handled.add(user)
            await member.edit(nick=None)
            await channel.send("Nickname has been removed")

    async def rename(self, channel, user, message_id, mod):
        """Set a new nickname for the user"""
        name = await Utils.get_username(self.bot, user)
        member = channel.guild.get_member(user)
        if member is None:
            await channel.send(f"{name} (``{user}``) is no longer on the server")
        else:
            await channel.send("Please enter a new nickname for the user:")
            try:
                message = await self.bot.wait_for("message", check=lambda m: m.author.id == mod.id, timeout=30)
            except futures.TimeoutError:
                await channel.send("No new nickname received, canceling")
            else:
                try:
                    self.handled.add(user)
                    await member.edit(nick=message.content)
                except discord.HTTPException as ex:
                    self.handled.remove(user)
                    await channel.send(f"Failed to set that nickname: {ex.text}")
                else:
                    await channel.send("Nickname set!")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if reaction.message.id in self.name_messages and user.id != self.bot.user.id and reaction.emoji in self.actions:
            await self.actions[reaction.emoji](reaction.message.channel, self.name_messages[reaction.message.id],
                                               reaction.message.id, user)


def setup(bot):
    bot.add_cog(BadNames(bot))
