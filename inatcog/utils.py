"""Utilities module."""
from urllib.parse import urlencode

from .base_classes import WWW_BASE_URL


async def get_valid_user_config(cog, ctx, anywhere=False):
    """Return iNat user config if known in this server.

    Note: Even if the user is known in another guild, they
    are not considered known anywhere until they permit it
    with `,user set known True`.
    """
    user_config = cog.config.user(ctx.author)
    inat_user_id = await user_config.inat_user_id()
    known_in = await user_config.known_in()
    known = inat_user_id and (
        ctx.guild.id in known_in or anywhere and await user_config.known_all()
    )
    if not known:
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
