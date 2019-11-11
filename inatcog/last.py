"""Module for handling recent history."""
from typing import NamedTuple
from datetime import datetime
import re
from discord import User

import timeago

from .api import get_observations
from .common import LOG
from .obs import get_obs_fields, PAT_OBS_LINK


class ObsLinkMsg(NamedTuple):
    """Discord & iNat fields from a recent observation link."""

    url: str
    obs: dict
    ago: str
    name: str


def get_last_obs_msg(msgs):
    """Find recent observation link."""
    found = None

    found = next(
        m for m in msgs if not m.author.bot and re.search(PAT_OBS_LINK, m.content)
    )
    LOG.info(repr(found))

    mat = re.search(PAT_OBS_LINK, found.content)
    obs_id = int(mat["obs_id"])
    url = mat["url"]
    ago = timeago.format(found.created_at, datetime.utcnow())
    if isinstance(found.author, User):
        name = found.author.name
    else:
        name = found.author.nick or found.author.name

    results = get_observations(obs_id, include_new_projects=True)["results"]
    obs = get_obs_fields(results[0]) if results else None

    return ObsLinkMsg(url, obs, ago, name)
