import asyncio
import os
import time
from datetime import datetime

import discord
from discord.ext import commands
from discord.ext.commands import MemberConverter, BadArgument, Greedy

from Util import Utils, Confirmation, Configuration, Logging
from Util.Converters import PotentialID, Reason


class Moderation:
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.trackers = dict()
        self.under_raid = dict()
        self.bad_names = []
        self.load_bad_names()
        # all raid info
        if not os.path.isdir("raids"):
            os.mkdir("raids")
            with open("raids/counter", "w") as file:
                file.write("0")

        # load last raid id
        with open("raids/counter") as file:
            self.last_raid = int(file.read())

    async def __local_check(self, ctx):
        return ctx.author.guild_permissions.ban_members

    def load_bad_names(self):
        if os.path.isfile("bad_names.txt"):
            with open("bad_names.txt", encoding="UTF-8") as namefile:
                self.bad_names = [line.rstrip().strip() for line in namefile.readlines()]
        else:
            with open("bad_names.txt", "w", encoding="UTF-8") as namefile:
                namefile.write(
                    "PLEASE REMOVE THIS LINE AND PUT ALL NAMES TO KICK UPON JOINING HERE, ONE NAME PER LINE, CASE INSENSITIVE")

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
        self.bot.loop.create_task(self._track(member))
        await self.check_name(member)

    async def _track(self, member):
        # grab the tracker
        guild_id = member.guild.id
        if guild_id not in self.trackers:
            self.trackers[guild_id] = list()

        tracker = self.trackers[guild_id]

        # start tracking
        tracker.append(member)

        # is there a raid going on?
        if guild_id in self.under_raid:
            await self._handle_raider(member)
        else:
            # do we have 5 people who in the last 3 seconds or 10 in 60 maybe??
            now = datetime.utcfromtimestamp(time.time())
            if len(tracker) >= 2 and (now - tracker[-2].joined_at).seconds <= 30 or \
                    len(tracker) >= 10 and (now - tracker[-10].joined_at).seconds <= 60:
                await self._sound_the_alarm(member.guild)

        await asyncio.sleep(60)

        # don't release anyone until the raid is over
        while guild_id in self.under_raid:
            await asyncio.sleep(1)
        tracker.remove(member)

    async def _handle_raider(self, member):
        guild_id = member.guild.id
        raid_info = self.under_raid[guild_id]
        raid_info["raiders"].append({
            "user_id": member.id,
            "user_name": str(member),
            "joined_at": str(member.joined_at)
        })
        raid_info["TODO"].append(member)
        await self.mute(member)

    async def _sound_the_alarm(self, guild):
        Logging.info(f"Sounding the alarm for {guild} ({guild.id})!")
        guild_id = guild.id

        # apply alarm, grab id later reference
        raid_id = self.last_raid = self.last_raid + 1
        with open("raids/counter", "w") as file:
            file.write(str(raid_id))
        self.under_raid[guild_id] = {
            "ID": raid_id,
            "guild": guild_id,
            "raiders": [],
            "message": None,
            "TODO": []
        }

        channel = self.bot.get_channel(Configuration.get_var(guild_id, f"MOD_CHANNEL"))
        if channel is not None:
            await channel.send(Configuration.get_var(guild_id, f"RAID_ALARM_MESSAGE"))
            await self.send_dash(channel, self.under_raid[guild_id])

        else:
            Logging.warn(f"Unable to sound the alarm in {guild.name} ({guild_id})")
            await guild.owner.send(
                f"🚨 Anti-raid alarm triggered for {guild.name} but the mod channel is misconfigured, please use ``!status`` somewhere in that server to get the raid status 🚨")

        # deal with current raiders
        for raider in self.trackers[guild.id]:
            await self._handle_raider(raider)

        self.bot.loop.create_task(self._alarm_checker(guild))

    async def _alarm_checker(self, guild):
        guild_id = guild.id
        tracker = self.trackers[guild_id]
        while guild_id in self.under_raid:
            now = datetime.utcfromtimestamp(time.time())
            # lift alarm when there are no new joins for 2 mins
            if (now - tracker[-1].joined_at).seconds >= 30:
                raid_info = self.under_raid[guild_id]
                Utils.save_to_disk(f"raids/{raid_info['ID']}", {k: v for k, v in raid_info.items() if k not in ["message", "TODO"]})
                Logging.info(f"Lifted alarm in {guild}")
                del self.under_raid[guild_id]
                channel = self.bot.get_channel(Configuration.get_var(guild_id, f"MOD_CHANNEL"))
                if channel is not None:
                    total = len(raid_info['raiders'])
                    left = len(raid_info["TODO"])
                    handled = total - left
                    await channel.send(f"Raid party is over :( Guess i'm done handing out special roles (for now).\n**Summary:**\nRaid ID: {raid_info['ID']}\n{total} guests showed up for the party\n{left} are still hanging out, enjoying that oh so special role they got\n{handled} are no longer with us.")
            else:
                await self._update_status(guild_id)
                asyncio.sleep(1)


    async def _update_status(self, guild):
        raid_info = self.under_raid[guild]
        await raid_info["message"].edit(content=self._get_message(raid_info))


    async def send_dash(self, channel, raid_info):
        message = await channel.send(self._get_message(raid_info))
        raid_info["message"] = message
        await message.add_reaction("🚪")
        await message.add_reaction("👢")
        await message.add_reaction("✖")
        return message



    def _get_message(self, raid_info):
        # assemble current status
        total = len(raid_info['raiders'])
        current = len(raid_info['TODO'])
        past = total - current
        return f"Total raiders: {total}\nRaiders already handled: {past}\nRaiders locked in for mod actions: {current}"

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
            for guild in self.bot.guilds:
                real_member = guild.get_member(member.id)
                if real_member is not None:
                    channel = self.bot.get_channel(Configuration.get_var(guild.id, "ACTION_CHANNEL"))
                    await real_member.kick(reason="Bad username")
                    if channel is not None:
                        await channel.send(f"Kicked {member} (``{member.id}``) for having a bad username")

    @commands.command()
    async def status(self, ctx):
        if ctx.guild.id in self.under_raid:
            await ctx.send("This server is being raided, everyone who joins now gets a special role and thrown into the report pool! :D")
            await self.send_dash(ctx, self.under_raid[ctx.guild.id])
        else:
            await ctx.send("I'm bored, there is no raid going on atm :(")


    async def on_reaction_add(self, reaction, user):
        guild_id = reaction.message.guild.id
        if guild_id in self.under_raid:
            raid_message = self.under_raid[guild_id]["message"]
            if reaction.message.id == raid_message.id:
                pass


def setup(bot):
    bot.add_cog(Moderation(bot))
