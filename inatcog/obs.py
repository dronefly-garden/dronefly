"""Module to work with iNat observations."""

from typing import NamedTuple
from .taxa import Taxon, get_taxon_fields


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
