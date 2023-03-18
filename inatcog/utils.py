"""Utilities module."""
import asyncio
from contextlib import asynccontextmanager
import functools
from typing import Optional, Union
from urllib.parse import urlencode

import discord
from dronefly.core.commands import Context as DroneflyContext
from dronefly.core.models.user import User as DroneflyUser
from redbot.core import commands, config

from .base_classes import COG_NAME, WWW_BASE_URL

COG_TO_CORE_USER_KEY = {
    "inat_user_id": "inat_user_id",
    "home": "inat_place_id",
    "lang": "inat_lang",
}
COG_HAS_USER_DEFAULTS = ["home"]


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
        async with cog.inat_client.set_ctx_from_user(context) as inat_client:
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


def get_cog(cog_or_ctx=Union[commands.Cog, commands.Context]) -> commands.Cog:
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
    dronefly_user = await get_dronefly_user(red_ctx, user or red_ctx.author, anywhere=anywhere)
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


async def get_dronefly_user_config(
    ctx: commands.Context,
    user: Optional[Union[discord.Member, discord.User]] = None,
    anywhere: bool = True,
) -> dict:
    """Return the config parameters for a Dronefly user.
    
    Supplies defaults from the guild and global configs if:
    - the Dronefly user is not known either globally or in the guild scope
      (i.e. anywhere=False vs. True)
    """
    cog = get_cog(ctx)
    global_config = cog.config
    guild_config = cog.config.guild(ctx.guild) if ctx.guild else None
    guild_config_dict = None
    global_config_dict = None
    try:
        user_config = await get_valid_user_config(ctx, user or ctx.author, anywhere)
        user_config_dict = await user_config.all()
    except LookupError:
        user_config_dict = None

    dronefly_config = {}
    for cog_key, core_key in COG_TO_CORE_USER_KEY.items():
        value = None
        if user_config_dict:
            value = user_config_dict.get(cog_key)
        if value is None and cog_key in COG_HAS_USER_DEFAULTS:
            guild_config_dict = guild_config_dict or await guild_config.all()
            value = guild_config.get(cog_key)
            if value is None:
                global_config_dict = global_config_dict or await global_config.all()
                value = global_config.get(cog_key)
        dronefly_config[core_key] = value
    return dronefly_config


async def get_dronefly_user(
    ctx: commands.Context,
    user: Optional[Union[discord.Member, discord.User]] = None,
    anywhere: bool = True,
) -> DroneflyUser:
    """Get a Dronefly user and their configuration in the current context."""
    dronefly_user_config = await get_dronefly_user_config(ctx, user, anywhere)
    return DroneflyUser(user.id if user else ctx.author.id, **dronefly_user_config)


async def get_home(
    ctx: commands.Context,
    user: Optional[Union[discord.Member, discord.User]] = None,
    anywhere: bool = True,
) -> dict:
    """Get configured home place for user."""
    dronefly_config = await get_dronefly_user_config(ctx, user, anywhere)
    return dronefly_config.get(COG_TO_CORE_USER_KEY["home"])


async def get_lang(
    ctx: commands.Context,
    user: Optional[Union[discord.Member, discord.User]] = None,
    anywhere: bool = True,
) -> dict:
    """Get configured preferred language for user."""
    dronefly_config = await get_dronefly_user_config(ctx, user, anywhere)
    return dronefly_config.get(COG_TO_CORE_USER_KEY["lang"])
