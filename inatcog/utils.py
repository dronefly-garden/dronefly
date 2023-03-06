"""Utilities module."""
import asyncio
from contextlib import asynccontextmanager
import functools
from typing import Optional, TYPE_CHECKING, Union
from urllib.parse import urlencode

import discord
from dronefly.core.commands import Context as DroneflyContext
from dronefly.core.models.user import User as DroneflyUser
from redbot.core import commands, config

from .base_classes import COG_NAME, WWW_BASE_URL
from .client import iNatClient


if TYPE_CHECKING:
    from redbot.core.commands import Context

    class ContextWithClient(Context):
        inat_client: iNatClient


def use_client(coro_or_command):
    is_command = isinstance(coro_or_command, commands.Command)
    if not is_command and not asyncio.iscoroutinefunction(coro_or_command):
        raise TypeError(
            "@use_client can only be used on commands or `async def` functions"
        )

    coro = coro_or_command.callback if is_command else coro_or_command

    @functools.wraps(coro)
    async def wrapped(*args, **kwargs):
        context: commands.Context = None
        cog: commands.Cog = None

        for arg in args:
            if isinstance(arg, commands.Context):
                context = arg
                cog = get_cog(context)
                break
        async with cog.inat_client.set_ctx(context, typing=True) as inat_client:
            context.inat_client = inat_client
            await coro(*args, **kwargs)

    if not is_command:
        return wrapped
    else:
        wrapped.__module__ = coro_or_command.callback.__module__
        coro_or_command.callback = wrapped
        return coro_or_command


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
    bot_attr = getattr(cog_or_ctx, "bot", None)
    cog = cog_or_ctx.bot.get_cog(COG_NAME) if bot_attr else cog_or_ctx
    if not cog:
        # Something is seriously wrong if we ever get here:
        raise discord.BadArugment(f"Cog not found: {COG_NAME}")
    return cog


async def get_dronefly_ctx(
    red_ctx: commands.Context,
    user: Optional[Union[discord.Member, discord.User]] = None,
    anywhere=True,
):
    _user = user or red_ctx.author
    user_config = await get_valid_user_config(red_ctx, _user, anywhere)
    inat_user_id = await user_config.inat_user_id() if user_config else None
    inat_place_id = await get_home(red_ctx, user_config=user_config)
    dronefly_user = DroneflyUser(
        id=_user.id,
        inat_user_id=inat_user_id,
        inat_place_id=inat_place_id,
    )

    return DroneflyContext(author=dronefly_user)


async def get_valid_user_config(
    cog_or_ctx: Union[commands.Cog, commands.Context],
    user: Union[discord.Member, discord.User],
    anywhere: bool = True,
):
    """Return iNat user config if known in this server.

    Note 1: Even if the user is known in another guild, they are not considered
    known anywhere until they permit it with `,user set known True`. This setting
    is ignored if anywhere=False (e.g. permission checks).

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
    cog_or_ctx: Union[commands.Cog, commands.Context],
    user: Union[discord.Member, discord.User],
    anywhere: bool = True,
):
    """Check if user is known in the specified scope.

    See Note 2 on get_valid_user_config() for how validity is determined (i.e.
    the config is considered valid even if the iNat account isn't)."""
    try:
        await get_valid_user_config(cog_or_ctx, user, anywhere)
    except LookupError:
        return False
    return True


@asynccontextmanager
async def valid_user_config(
    cog_or_ctx: Union[commands.Cog, commands.Context],
    user: Union[discord.Member, discord.User],
    anywhere: bool = True,
):
    user_config = None
    try:
        user_config = await get_valid_user_config(cog_or_ctx, user, anywhere)
    except LookupError:
        pass
    yield user_config


async def get_home(
    ctx,
    user: Optional[Union[discord.Member, discord.User]] = None,
    user_config: Optional[config.Group] = None,
):
    """Get configured home place for author."""
    home = None
    _user = user or ctx.author

    if user_config:
        home = await user_config.home()
    else:
        async with valid_user_config(ctx, _user) as config:
            if config:
                home = await config.home()
    if not home:
        cog = get_cog(ctx)
        if ctx.guild:
            guild_config = cog.config.guild(ctx.guild)
            home = await guild_config.home()
        else:
            home = await cog.config.home()
    return home


async def get_lang(
    ctx,
    user: Optional[Union[discord.Member, discord.User]] = None,
    user_config: Optional[config.Group] = None,
):
    """Get configured preferred language for author."""
    lang = None
    _user = user or ctx.author
    if user_config:
        lang = await user_config.lang()
    else:
        async with valid_user_config(ctx, _user) as config:
            if config:
                lang = await config.lang()
    # TODO: support guild and global preferred language
    # if not lang:
    #    cog = get_cog(ctx)
    #    if ctx.guild:
    #        guild_config = cog.config.guild(ctx.guild)
    #        lang = await guild_config.lang()
    #    else:
    #        lang = await cog.config.lang()
    return lang
