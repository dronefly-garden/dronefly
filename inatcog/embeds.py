"""Module to make embeds."""
import discord

EM_COLOR = 0x90EE90


def make_embed(**kwargs):
    """Make a standard embed for this cog."""
    return discord.Embed(color=EM_COLOR, **kwargs)


def sorry(apology="I don't understand"):
    """Notify user their request could not be satisfied."""
    return make_embed(title="Sorry", description=apology)
