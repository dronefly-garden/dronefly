"""Module for handling recent history."""
from typing import NamedTuple
from datetime import datetime
import re
from discord import User

import timeago

from .api import get_observations, get_taxa, WWW_BASE_URL
from .common import LOG
from .obs import get_obs_fields, PAT_OBS_LINK
from .taxa import get_taxon_fields, PAT_TAXON_LINK


class ObsLinkMsg(NamedTuple):
    """Discord & iNat fields from a recent observation link."""

    url: str
    obs: dict
    ago: str
    name: str


class TaxonLinkMsg(NamedTuple):
    """Discord & iNat fields from a recent taxon link."""

    url: str
    taxon: dict


def get_last_obs_msg(msgs):
    """Find recent observation link."""
    found = None

    # Skip bot messages so we can extract the user info for the user who shared it
    found = next(
        m for m in msgs if not m.author.bot and re.search(PAT_OBS_LINK, m.content)
    )
    LOG.info(repr(found))

    mat = re.search(PAT_OBS_LINK, found.content)
    obs_id = int(mat["obs_id"] or mat["cmd_obs_id"])
    url = mat["url"] or WWW_BASE_URL + "/observations/" + str(obs_id)
    ago = timeago.format(found.created_at, datetime.utcnow())
    if isinstance(found.author, User):
        name = found.author.name
    else:
        name = found.author.nick or found.author.name

    results = get_observations(obs_id, include_new_projects=True)["results"]
    obs = get_obs_fields(results[0]) if results else None

    return ObsLinkMsg(url, obs, ago, name)


async def get_last_taxon_msg(msgs):
    """Find recent taxon link."""
    found = None

    def match_taxon_link(message):
        return re.search(PAT_TAXON_LINK, message.content) or (
            message.embeds
            and message.embeds[0].url
            and re.search(PAT_TAXON_LINK, message.embeds[0].url)
        )

    # - Include bot msgs because that's mostly how users share these links,
    #   and we're not interested in who shared the link in this case.
    # - If the message is from a bot, it's likely an embed, so search the
    #   url (only 1st embed for the message is checked).
    found = next(m for m in msgs if match_taxon_link(m))
    LOG.info(repr(found))

    mat = match_taxon_link(found)
    taxon_id = int(mat["taxon_id"])
    url = mat["url"] or WWW_BASE_URL + "/taxa/" + str(taxon_id)

    results = (await get_taxa(taxon_id))["results"]
    taxon = get_taxon_fields(results[0]) if results else None

    return TaxonLinkMsg(url, taxon)
