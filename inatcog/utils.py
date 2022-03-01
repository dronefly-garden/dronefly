"""Utilities module."""
from typing import Union
from urllib.parse import urlencode

import discord

from .base_classes import WWW_BASE_URL
from .common import LOG


async def get_valid_user_config(
    cog, user=Union[discord.Member, discord.User], anywhere=True
):
    """Return iNat user config if known in this server.

    Note: Even if the user is known in another guild, they
    are not considered known anywhere until they permit it
    with `,user set known True`.
    """
    user_config = cog.config.user(user)
    LOG.info(user.id)
    inat_user_id = await user_config.inat_user_id()
    if not inat_user_id:
        return False
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
