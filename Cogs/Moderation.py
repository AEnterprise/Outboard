import asyncio
import datetime
import os

import discord
from discord.ext import commands
from discord.ext.commands import MemberConverter, BadArgument, Greedy

from Util import Utils, Confirmation, Configuration, Logging
from Util.Converters import PotentialID, Reason


class Moderation:
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.trackers = dict(WARNING=dict(), ALARM=dict())
        self.active = dict(WARNING=set(), ALARM=set())
        self.bad_names = []
        self.load_bad_names()

    async def __local_check(self, ctx):
        return ctx.author.guild_permissions.ban_members

    def load_bad_names(self):
        if os.path.isfile("bad_names.txt"):
            with open("bad_names.txt", encoding="UTF-8") as namefile:
                self.bad_names = [line.rstrip().strip() for line in namefile.readlines()]
        else:
            with open("bad_names.txt", "w", encoding="UTF-8") as namefile:
                namefile.write("PLEASE REMOVE THIS LINE AND PUT ALL NAMES TO KICK UPON JOINING HERE, ONE NAME PER LINE, CASE INSENSITIVE")

    @staticmethod
    def _can_act(ctx, user: discord.Member):
        if (ctx.author != user and user != ctx.bot.user and ctx.author.top_role > user.top_role) or \
                (ctx.guild.owner == ctx.author and ctx.author != user):
            if ctx.me.top_role > user.top_role:
                return True, None
            else:
                return False, f"Unable to ban {user} as I do not have a higher role than them."
        else:
            return False, f"You are not allowed to ban {user}."

    @commands.guild_only()
    @commands.command()
    @commands.bot_has_permissions(ban_members=True)
    async def mban(self, ctx, targets: Greedy[PotentialID], *, reason: Reason = ""):
        """mban_help"""
        if reason == "":
            reason = "No reason specified"

        async def yes():
            pmessage = await ctx.send("🔁 Processing")
            valid = 0
            failures = []
            for t in targets:
                try:
                    member = await MemberConverter().convert(ctx, str(t))
                except BadArgument:
                    user = discord.Object(t)
                    try:
                        await ctx.guild.ban(user,
                                            reason=f"Moderator: {ctx.author.name} ({ctx.author.id}) Reason: {reason}",
                                            delete_message_days=0)
                    except discord.NotFound as bad:
                        failures.append(f"``{t}``: Unable to convert to a user")
                    else:

                        valid += 1
                else:
                    allowed, message = self._can_act(ctx, member)
                    if allowed:
                        await ctx.guild.ban(member,
                                            reason=f"Moderator: {ctx.author.name} ({ctx.author.id}) Reason: {reason}",
                                            delete_message_days=0)
                        valid += 1
                    else:
                        failures.append(f"``{t}``: {message}")
            await pmessage.delete()
            await ctx.send(f"✅ Successfully banned {valid} people.")
            if len(failures) > 0:
                test = "\n"
                for page in Utils.paginate(f"🚫 I failed to ban the following users:\n{test.join(failures)}"):
                    await ctx.send(page)

        await Confirmation.confirm(ctx, "Are you sure you want to ban all those people?", on_yes=yes)

    async def on_member_join(self, member: discord.Member):
        self.bot.loop.create_task(self.track_for("WARNING", member))
        self.bot.loop.create_task(self.track_for("ALARM", member))
        await self.check_name(member)

    async def track_for(self, kind, member):
        guild = member.guild
        tracker = self.trackers[kind]
        if guild.id not in tracker:
            tracker[guild.id] = set()
        tracker[guild.id].add(member)
        amount = Configuration.get_var(guild.id, f"RAID_{kind}_AMOUNT")
        if len(tracker[guild.id]) >= amount:
            if guild.id not in self.active[kind]:
                self.active[kind].add(guild.id)
                await self.sound_the(kind, guild)
            if kind == "ALARM":
                await self.mute(member)
        await asyncio.sleep(Configuration.get_var(guild.id, f"RAID_{kind}_TIMEFRAME"))
        tracker[guild.id].remove(member)
        if len(tracker[guild.id]) < amount and guild.id in self.active[kind]:
            self.active[kind].remove(guild.id)
            Logging.info(f"{kind} lifted for {guild.name}")
            channel = self.bot.get_channel(Configuration.get_var(guild.id, f"MOD_CHANNEL"))
            if channel is not None:
                await channel.send(f"{kind} has been lifted")

    async def sound_the(self, kind, guild):
        Logging.info(f"Anti-raid {kind} triggered for {guild.name} ({guild.id})!")
        channel = self.bot.get_channel(Configuration.get_var(guild.id, f"MOD_CHANNEL"))
        if channel is not None:
            await channel.send(Configuration.get_var(guild.id, f"RAID_{kind}_MESSAGE"))
        else:
            Logging.warn(f"Unable to sound the {kind} in {guild.name} ({guild.id})")
            await guild.owner.send(
                f"🚨 Anti-raid {kind} triggered for {guild.name} but the mod channel is misconfigured 🚨")
        if kind == "ALARM":
            for m in self.trackers[kind][guild.id]:
                await self.mute(m)

    async def mute(self, member):
        role = member.guild.get_role(Configuration.get_var(member.guild.id, "MUTE_ROLE"))
        if role is not None:
            try:
                await member.add_roles(role, reason="Raid alarm triggered")
            except discord.HTTPException:
                Logging.warn(f"failed to mute {member} ({member.id}!")

    async def on_member_update(self, before, after):
        if before.nick != after.nick or before.name != after.name:
            await self.check_name(after)

    async def check_name(self, member):
        if member.nick is not None:
            nick = member.nick.lower()
            if any(bad in nick for bad in self.bad_names):
                await member.edit(nick="Squeaky clean")
        name = member.name.lower()
        if any(bad in name for bad in self.bad_names):
            channel = self.bot.get_channel(Configuration.get_var(member.guild.id, "ACTION_CHANNEL"))
            await member.kick(reason="Bad username")
            if channel is not None:
                await channel.send(f"Kicked {member} (``{member.id}``) for having a bad username")


def setup(bot):
    bot.add_cog(Moderation(bot))
