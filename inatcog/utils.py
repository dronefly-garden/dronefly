"""Utilities module."""
from typing import Union
from urllib.parse import urlencode

import discord
from redbot.core import commands

from .base_classes import COG_NAME, WWW_BASE_URL


def obs_url_from_v1(params: dict):
    """Observations query URL corresponding to /v1/observations API params."""
    url = WWW_BASE_URL + "/observations"
    if params:
        if "observed_on" in params:
            _params = params.copy()
            _params["on"] = params["observed_on"]
            del _params["observed_on"]
        else:
            _params = params
        url += "?" + urlencode(_params)
    return url

def get_cog(cog_or_ctx=Union[commands.Cog, commands.Context]):
    cog = cog_or_ctx.bot.get_cog(COG_NAME) if isinstance(cog_or_ctx, commands.Context) else cog_or_ctx
    if not cog:
        # Something is seriously wrong if we ever get here:
        raise discord.BadArugment(f"Cog not found: {COG_NAME}")
    return cog

async def get_valid_user_config(
    cog_or_ctx=Union[commands.Cog, commands.Context], user=Union[discord.Member, discord.User], anywhere=True
):
    """Return iNat user config if known in this server.

    Note 1: Even if the user is known in another guild, they are not considered
    known anywhere until they permit it with `,user set known True`.

    Note 2: A user may be registered to a certain user id#, but the id# is
    invalid (e.g. account deleted). If that is the case, they'll still have
    access to functions that only require that their user ID be known to the
    bot!
    """
    cog = get_cog(cog_or_ctx)
    user_config = cog.config.user(user)
    inat_user_id = await user_config.inat_user_id()
    if not inat_user_id:
        known_here = False
    else:
        known_in = await user_config.known_in()
        if isinstance(user, discord.Member):
            known_here = user.guild.id in known_in
            if anywhere and not known_here:
                known_here = bool(await user_config.known_all())
        else:
            # always known in DM so long as `,user add` has been performed anywhere
            known_here = bool(known_in)
    if not known_here:
        where = "" if anywhere else " in this server"
        raise LookupError(f"iNat user not known{where}.")
    return user_config

async def has_valid_user_config(
    cog_or_ctx=Union[commands.Cog, commands.Context], user=Union[discord.Member, discord.User], anywhere=True
):
    """Check if user is known in the specified scope.

    See Note 2 on get_valid_user_config() for how validity is determined (i.e.
    the config is considered valid even if the iNat account isn't)."""
    try:
        await get_valid_user_config(cog_or_ctx, user, anywhere)
    except LookupError:
        return False
    return True

async def get_home(ctx):
    """Get configured home place for author."""
    user_config = await get_valid_user_config(ctx, ctx.author, anywhere=False)
    if user_config:
        home = await user_config.home()
    if not home:
        cog = get_cog(ctx)
        if ctx.guild:
            guild_config = cog.config.guild(ctx.guild)
            home = await guild_config.home()
        else:
            home = await cog.config.home()
    return home

async def get_lang(ctx):
    """Get configured preferred language for author."""
    user_config = await get_valid_user_config(ctx, ctx.author, anywhere=False)
    if user_config:
        lang = await user_config.lang()
    # TODO: support guild and global preferred language
    # if not lang:
    #    if ctx.guild:
    #        guild_config = self.config.guild(ctx.guild)
    #        lang = await guild_config.lang()
    #    else:
    #        lang = await self.config.lang()
    return lang
