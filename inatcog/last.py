"""Module for handling recent history."""
from datetime import datetime
import re
from typing import NamedTuple

from discord import User
import timeago

from .base_classes import WWW_BASE_URL
from .core.parsers.url import PAT_OBS_LINK, PAT_TAXON_LINK
from .obs import get_obs_fields
from .taxa import get_taxon


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

    def __init__(self, cog):
        self.cog = cog

    async def get_last_obs_msg(self, ctx, msgs):
        """Find recent observation link."""

        def match_obs_link(message):
            return re.search(PAT_OBS_LINK, message.content) or (
                message.embeds
                and message.embeds[0].url
                and re.search(PAT_OBS_LINK, message.embeds[0].url)
            )

        try:
            found = next(m for m in msgs if match_obs_link(m))
        except StopIteration:
            return None

        mat = match_obs_link(found)
        obs_id = int(mat["obs_id"])
        url = mat["url"] or WWW_BASE_URL + "/observations/" + str(obs_id)
        ago = timeago.format(found.created_at, datetime.utcnow())
        if found.author.bot:
            name = None
        else:
            # Unless autoobs is turned off, it's more likely the
            # bot message for the shared link will be found first.
            if isinstance(found.author, User):
                name = found.author.name
            else:
                name = found.author.nick or found.author.name

        home = await self.cog.get_home(ctx)
        results = (
            await self.cog.api.get_observations(
                obs_id, include_new_projects=1, preferred_place_id=home
            )
        )["results"]
        obs = get_obs_fields(results[0]) if results else None

        return ObsLinkMsg(url, obs, ago, name)

    async def get_last_taxon_msg(self, ctx, msgs):
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
        home = await self.cog.get_home(ctx)
        taxon = await get_taxon(self.cog, taxon_id, preferred_place_id=home)

        return TaxonLinkMsg(url, taxon)
