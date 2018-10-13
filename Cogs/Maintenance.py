from discord.ext import commands

# Maintencance stuff, locked to owner only
from Util import Utils, Logging, Configuration


class Maintenance:
    def __init__(self, bot):
        self.bot: commands.Bot = bot

    async def __local_check(self, ctx):
        return await ctx.bot.is_owner(ctx.author)

    @commands.command()
    async def restart(self, ctx):
        """Restarts the bot"""
        await ctx.send("Restarting...")
        await Utils.clean_exit(self.bot, ctx.author.name)

    @commands.command(hidden=True)
    async def upgrade(self, ctx):
        await ctx.send(
            "<:BCWrench:344163417981976578> I'll be right back with new gears! <:woodGear:344163118089240596> <:stoneGear:344163146325295105> <:ironGear:344163170664841216> <:goldGear:344163202684289024> <:diamondGear:344163228101640192>")
        await Logging.bot_log(f"Upgrade initiated by {ctx.author.name}")
        Logging.info(f"Upgrade initiated by {ctx.author.name}")
        await ctx.invoke(self.pull)
        await ctx.invoke(self.restart)

    @commands.command()
    async def reloadconfigs(self, ctx: commands.Context):
        """Reloads all server configs from disk"""
        async with ctx.typing():
            Configuration.load_master()
            await Configuration.on_ready(self.bot)
        await ctx.send("Configs reloaded")

    @commands.command()
    async def pull(self, ctx):
        """Pulls from github so an upgrade can be performed without full restart"""
        async with ctx.typing():
            code, out, error = await Utils.execute(["git pull origin master"])
        if code is 0:
            await ctx.send(
                f"✅ Pull completed with exit code {code}```yaml\n{out.decode('utf-8')}```")
        else:
            await ctx.send(
                f"🚫 Pull completed with exit code {code}```yaml\n{out.decode('utf-8')}\n{error.decode('utf-8')}```")


def setup(bot):
    bot.add_cog(Maintenance(bot))
