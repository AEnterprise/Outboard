import re

from discord.ext import commands

from Util import Configuration, Utils


class BadNames:

    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.detectors = dict()
        for guild in bot.guilds:
            self.assemble_detector(guild)

    def assemble_detector(self, guild):
        bad_names = Configuration.get_master_var(guild.id, "BAD_NAMES")
        capture = "|".join(bad_names)
        self.detectors[guild.id] = re.compile(f"({capture})", flags=re.IGNORECASE)

    async def on_member_update(self, before, after):
        if before.nick != after.nick or before.name != after.name:
            await self.check_name(after)

    async def check_name(self, member):
        # no detector means nothing on the blacklist to check against
        if member.guild.id not in self.detectors:
            return

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

                    # track selfbots and others who don't get the hint
                    if guild.id not in self.kick_trackers:
                        self.kick_trackers[guild.id] = deque(maxlen=10)
                    tracker = self.kick_trackers[guild.id]
                    tracker.append(member.id)
                    # boot them out, grab the hammer if they don't get the hint (or use auto-joining self-bot)
                    if tracker.count(member.id) >= 5:
                        await real_member.ban(Reason="Too many bad names, didn't get the hint")
                        message = f"Banned {member} ({member.id}) as they kept returning with a bad name"
                    else:
                        await real_member.kick(reason="Bad username")
                        message = f"Kicked {member} (``{member.id}``) for having a bad username"
                    if channel is not None:
                        await channel.send(message)

    def get_matches(self, guild_id, name):
        return self.detectors[guild_id].findall(name) if guild_id in self.detectors else []

    def get_matches_pretty(self, guild_id, name):
        return (name.replace(match, f"**{match}**") for match in self.get_matches(guild_id, name))

    @commands.group()
    async def blacklist(self, ctx):
        # TODO: show help instead
        pass

    @blacklist.command()
    async def show(self, ctx):
        bad_names = Configuration.get_master_var(ctx.guild.id, "BAD_NAMES")
        pages = Utils.paginate('\n'.join(bad_names), prefix="Blacklist entries (part {page}/{pages}:```\n",
                               suffix="\n```")
        # TODO: confirmation if there are too many entries? Not sure we'll ever 100+ entries
        for page in pages:
            await ctx.send(page)

    @blacklist.command("add")
    async def blacklist_add(self, ctx, *, entry: str):
        guild_id = ctx.guild.id
        existing_matches = self.get_matches_pretty(guild_id, entry)
        if existing_matches:
            out = '\n'.join(existing_matches)
            await ctx.send(f"This name is already covered with existing entries: \n{out}")
        else:
            blacklist = Configuration.get_master_var(guild_id, "BAD_NAMES")
            blacklist.append(entry)
            Configuration.save(guild_id)
            await ctx.send(f"``{entry}`` has been added to the blacklist")

    @blacklist.command("remove")
    async def blacklist_remove(self, ctx, *, entry: str):
        guild_id = ctx.guild.id
        blacklist = Configuration.get_master_var(guild_id, "BAD_NAMES")
        if entry in blacklist:
            blacklist.remove(entry)
            Configuration.save(guild_id)
            await ctx.send(f"``{entry}`` has been removed from the blacklist")
        else:
            # check if it's matched under something else
            matches = self.get_matches(guild_id, entry)
            if matches:
                await ctx.send(f"")


def setup(bot):
    bot.add_cog(BadNames(bot))
