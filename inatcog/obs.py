"""Module to work with iNat observations."""

import re
from typing import NamedTuple

from .taxa import Taxon, get_taxon_fields
from .users import User, get_user_from_json

PAT_OBS_LINK = re.compile(
    r"\b(?P<url>https?://(www\.)?inaturalist\.(org|ca)/observations/(?P<obs_id>\d+))\b",
    re.I,
)


class Obs(NamedTuple):
    """An observation."""

    taxon: Taxon or None
    obs_id: int
    obs_on: str or None
    obs_at: str or None
    user: User
    thumbnail: str or None


def get_obs_fields(record):
    """Get an Obs from get_observations JSON record.

    Parameters
    ----------
    record: dict
        A JSON observation record from /v1/observations or other endpoint
        returning observations.

    Returns
    -------
    Obs
        An Obs object from the JSON results.
    """

    community_taxon = record.get("community_taxon")
    rec_taxon = community_taxon or record.get("taxon")
    if rec_taxon:
        taxon = get_taxon_fields(rec_taxon)
    else:
        taxon = None

    obs_id = record["id"]
    obs_on = record.get("observed_on_string") or None
    obs_at = record.get("place_guess") or None
    user = get_user_from_json(record["user"])

    photos = record.get("photos")
    if photos:
        thumbnail = photos[0].get("url")
    else:
        thumbnail = None

    return Obs(taxon, obs_id, obs_on, obs_at, user, thumbnail)
