"""Module for handling recent history."""
from typing import NamedTuple
from datetime import datetime
import re
from discord import User

import timeago

from .api import WWW_BASE_URL
from .obs import get_obs_fields
from .obs_classes import PAT_OBS_LINK
from .taxa import get_taxon, PAT_TAXON_LINK


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


class INatLinkMsg:
    """Get INat link message from channel history supplemented with info from iNat."""

    def __init__(self, api):
        self.api = api

    async def get_last_obs_msg(self, msgs):
        """Find recent observation link."""
        # Skip bot messages so we can extract the user info for the user who shared it
        try:
            found = next(
                m
                for m in msgs
                if not m.author.bot and re.search(PAT_OBS_LINK, m.content)
            )
        except StopIteration:
            return None

        mat = re.search(PAT_OBS_LINK, found.content)
        obs_id = int(mat["obs_id"] or mat["cmd_obs_id"])
        url = mat["url"] or WWW_BASE_URL + "/observations/" + str(obs_id)
        ago = timeago.format(found.created_at, datetime.utcnow())
        if isinstance(found.author, User):
            name = found.author.name
        else:
            name = found.author.nick or found.author.name

        results = (await self.api.get_observations(obs_id, include_new_projects=1))[
            "results"
        ]
        obs = get_obs_fields(results[0]) if results else None

        return ObsLinkMsg(url, obs, ago, name)

    async def get_last_taxon_msg(self, msgs):
        """Find recent taxon link."""

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
        try:
            found = next(m for m in msgs if match_taxon_link(m))
        except StopIteration:
            return None

        mat = match_taxon_link(found)
        taxon_id = int(mat["taxon_id"])
        url = mat["url"] or WWW_BASE_URL + "/taxa/" + str(taxon_id)

        taxon = await get_taxon(self, taxon_id)

        return TaxonLinkMsg(url, taxon)
