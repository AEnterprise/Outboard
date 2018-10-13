import asyncio

import discord
from discord.ext import commands


async def confirm(ctx: commands.Context, text, timeout=30, on_yes=None, on_no=None, delete=True):
    message: discord.Message = await ctx.send(text)
    await message.add_reaction("✅")
    await message.add_reaction("🚫")

    def check(reaction: discord.Reaction, user):
        return user == ctx.message.author and reaction.emoji in ("✅", "🚫") and reaction.message.id == message.id

    try:
        reaction, user = await ctx.bot.wait_for('reaction_add', timeout=timeout, check=check)
    except asyncio.TimeoutError:
        await message.delete()
        await ctx.send(f"I got no answer within {timeout} seconds.. Aborting.")
    else:
        if reaction.emoji == "✅" and on_yes is not None:
            if delete:
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
            await on_yes()
        elif reaction.emoji == "🚫":
            if delete:
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
            if on_no is not None:
                await on_no()
            else:
                await ctx.send("🚫 Command execution canceled")
