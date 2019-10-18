"""Module to work with iNat observations."""

import re
from typing import NamedTuple

from .common import LOG
from .embeds import make_embed
from .taxa import Taxon, format_taxon_name, get_taxon_fields

PAT_OBS_LINK = re.compile(
    r"\b(?P<url>https?://(www\.)?inaturalist\.(org|ca)/observations/(?P<obs_id>\d+))\b",
    re.I,
)


class Obs(NamedTuple):
    """A flattened representation of a single get_observations JSON result."""

    taxon: Taxon or None
    obs_id: str
    obs_on: str or None
    obs_by: str
    thumbnail: str or None


def get_obs_fields(record):
    """Map a get_observations JSON record into a tuple of selected fields.

    Parameters
    ----------
    record: dict
        A JSON observation record from /v1/observations.

    Returns
    -------
    Obs
        An Obs tuple containing a subset of fields from the full
        JSON results.
    """

    community_taxon = record.get("community_taxon")
    rec_taxon = community_taxon or record.get("taxon")
    if rec_taxon:
        taxon = get_taxon_fields(rec_taxon)
    else:
        taxon = None

    obs_id = record["id"]
    obs_on = record.get("observed_on_string") or None

    user = record["user"]
    by_name = user.get("name")
    by_login = user.get("login")
    obs_by = by_name or by_login or "Somebody"

    photos = record.get("photos")
    if photos:
        thumbnail = photos[0].get("url")
    else:
        thumbnail = None

    return Obs(taxon, obs_id, obs_on, obs_by, thumbnail)


def make_obs_embed(obs, url):
    """Return embed for an observation link."""
    embed = make_embed(url=url)
    summary = None

    if obs:
        taxon = obs.taxon
        if taxon:
            embed.title = format_taxon_name(taxon)
        else:
            embed.title = "Unknown"
        if obs.thumbnail:
            embed.set_thumbnail(url=obs.thumbnail)
        if obs.obs_on:
            summary = "Observed by %s on %s" % (obs.obs_by, obs.obs_on)
        else:
            summary = "Observed by %s" % obs.obs_by
        embed.description = summary
    else:
        mat = re.search(PAT_OBS_LINK, url)
        obs_id = int(mat["obs_id"])
        LOG.info("Observation not found for link: %d", obs_id)
        embed.title = "No observation found for id: %d (deleted?)" % obs_id

    return embed
