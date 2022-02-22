"""Utilities module."""
from urllib.parse import urlencode

from .base_classes import WWW_BASE_URL


async def get_valid_user_config(cog, ctx):
    """iNat user config known in this guild."""
    user_config = cog.config.user(ctx.author)
    inat_user_id = await user_config.inat_user_id()
    known_in = await user_config.known_in()
    known_all = await user_config.known_all()
    if not (inat_user_id and known_all or ctx.guild.id in known_in):
        raise LookupError("Ask a moderator to add your iNat profile link.")
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
