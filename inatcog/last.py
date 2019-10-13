"""Module for handling recent history."""
from collections import namedtuple
from datetime import datetime
import re

import discord
import timeago

from .common import EM_COLOR, LOG
from .api import get_observations

PAT_OBS = re.compile(
    r'\b(?P<url>https?://(www\.)?inaturalist\.(org|ca)/observations/(?P<obs_id>\d+))\b',
    re.I,
)

ObsLinkMsg = namedtuple('ObsLinkMsg', 'url, obs, ago, name')
def get_last_obs_msg(msgs):
    """Find recent observation link."""
    found = None

    found = next(m for m in msgs if not m.author.bot and re.search(PAT_OBS, m.content))
    LOG.info(repr(found))

    mat = re.search(PAT_OBS, found.content)
    obs_id = int(mat["obs_id"])
    url = mat["url"]
    ago = timeago.format(found.created_at, datetime.utcnow())
    name = found.author.nick or found.author.name
    results = get_observations(obs_id)["results"]
    obs = results[0] if results else None

    return ObsLinkMsg(url, obs, ago, name)

def last_obs_embed(last):
    """Return embed for recent observation link."""
    embed = discord.Embed(color=EM_COLOR)
    embed.url = last.url
    summary = None

    if last:
        obs = last.obs
        community_taxon = obs.get("community_taxon")
        taxon = community_taxon or obs.get("taxon")
        if taxon:
            sci_name = taxon["name"]
            common = taxon.get("preferred_common_name")
            embed.title = '%s (%s)' % (sci_name, common) if common else sci_name
        else:
            embed.title = str(obs["obs_id"])
        photos = obs.get("photos")
        if photos:
            thumbnail = photos[0].get("url")
        else:
            thumbnail = None
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        observed_on = obs.get("observed_on_string")
        user = obs["user"]
        by_name = user.get("name")
        by_login = user.get("login")
        observed_by = by_name or by_login or "Somebody"
        if observed_on:
            summary = 'Observed by %s on %s' % (observed_by, observed_on)
    else:
        LOG.info('Deleted observation: %d', obs["obs_id"])
        embed.title = 'Deleted'

    embed.add_field(
        name=summary or '\u200B', value='shared %s by @%s' % (last.ago, last.name)
    )
    return embed

