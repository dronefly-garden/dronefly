"""Module to make embeds."""
from functools import wraps
import discord
from .common import make_decorator

EMBED_COLOR = 0x90EE90
# From https://discordapp.com/developers/docs/resources/channel#embed-limits
MAX_EMBED_TITLE_LEN = MAX_EMBED_NAME_LEN = 256
MAX_EMBED_DESCRIPTION_LEN = 2048
MAX_EMBED_FIELDS = 25
MAX_EMBED_VALUE_LEN = 1024
MAX_EMBED_FOOTER_LEN = 2048
MAX_EMBED_AUTHOR_LEN = 256
MAX_EMBED_LEN = 6000


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


def sorry(apology="I don't understand"):
    """Notify user their request could not be satisfied."""
    return make_embed(title="Sorry", description=apology)
