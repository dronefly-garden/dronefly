"""Module to make embeds."""
import asyncio
import contextlib
from functools import wraps
from typing import Iterable, Union

import discord
from redbot.core.commands import Context
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

from inatcog.common import make_decorator

EMBED_COLOR = 0x90EE90
# From https://discordapp.com/developers/docs/resources/channel#embed-limits
MAX_EMBED_TITLE_LEN = MAX_EMBED_NAME_LEN = 256
MAX_EMBED_DESCRIPTION_LEN = 2048
MAX_EMBED_FIELDS = 25
MAX_EMBED_VALUE_LEN = 1024
MAX_EMBED_FOOTER_LEN = 2048
MAX_EMBED_AUTHOR_LEN = 256
MAX_EMBED_LEN = 6000
# It's not exactly 2**23 due to overhead, but how much less, we can't determine.
# This is a safe value that works for others.
MAX_EMBED_FILE_LEN = 8000000


class NoRoomInDisplay(Exception):
    """Size of embed exceeded."""


async def apologize(ctx, apology="I don't understand"):
    """Send an apology and remove the message after a while."""
    if ctx.guild and ctx.channel.permissions_for(ctx.guild.me).embed_links:
        msg = await ctx.send(embed=sorry(apology=apology, title="Sorry"))
    else:
        msg = await ctx.send(f"Sorry: {apology}")
    await asyncio.sleep(30)
    with contextlib.suppress(discord.HTTPException):
        await msg.delete()


@make_decorator
def format_items_for_embed(function, max_len=MAX_EMBED_NAME_LEN):
    """Format items as delimited list not exceeding Discord length limits."""

    @wraps(function)
    def wrap_format_items_for_embed(*args, **kwargs):
        kwargs["max_len"] = max_len
        return function(*args, **kwargs)

    return wrap_format_items_for_embed


def make_embed(**kwargs):
    """Make a standard embed for this cog."""
    return discord.Embed(color=EMBED_COLOR, **kwargs)


def sorry(apology="I don't understand", title="Sorry"):
    """Notify user their request could not be satisfied."""
    return make_embed(title=title, description=apology)


async def add_reactions_with_cancel(
    ctx: Context,
    msg: discord.Message,
    emojis: Iterable[Union[str, discord.Emoji]],
    timeout: int = 30,
    with_keep: bool = False,
):
    """Add reactions with, for a limited time, author-only cancel."""
    _emojis = [emojis] if isinstance(emojis, str) else list(emojis)
    extra_emojis = []
    cancel = "\N{CROSS MARK}"
    _emojis.append(cancel)
    extra_emojis.append(cancel)
    if with_keep:
        keep = "\N{WHITE HEAVY CHECK MARK}"
        _emojis.append(keep)
        extra_emojis.append(keep)
    start_adding_reactions(msg, _emojis)
    pred = ReactionPredicate.with_emojis(extra_emojis, msg, user=ctx.author)

    try:
        await ctx.bot.wait_for("reaction_add", check=pred, timeout=timeout)
        if pred.result == 0:
            with contextlib.suppress(discord.HTTPException):
                await msg.delete()
                return True
    except asyncio.TimeoutError:
        pass
    with contextlib.suppress(discord.HTTPException):
        for emoji in extra_emojis:
            await msg.clear_reaction(emoji)
    return False
