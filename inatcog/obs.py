"""Module to work with iNat observations."""

import re
from typing import NamedTuple

from .common import LOG
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
    quality_grade: str or None
    idents_agree: int
    idents_count: int
    faves: int


def get_obs_fields(obs):
    """Get an Obs from get_observations JSON record.

    Parameters
    ----------
    obs: dict
        A JSON observation record from /v1/observations or other endpoint
        returning observations.

    Returns
    -------
    Obs
        An Obs object from the JSON results.
    """

    community_taxon = obs.get("community_taxon")
    obs_taxon = community_taxon or obs.get("taxon")
    if obs_taxon:
        taxon = get_taxon_fields(obs_taxon)
    else:
        taxon = None

    obs_id = obs["id"]
    obs_on = obs.get("observed_on_string") or None
    obs_at = obs.get("place_guess") or None
    quality_grade = obs.get("quality_grade")
    user = get_user_from_json(obs["user"])

    idents_count = obs["identifications_count"]
    idents_agree = obs["num_identification_agreements"]
    if idents_count > 1:
        LOG.info("community taxon.id = %d", obs_taxon["id"])
        LOG.info("idents_count = %d", idents_count)
        ident_taxon_ids = obs["ident_taxon_ids"]
        identifications = obs["identifications"]
        observer_taxon_id = observer_taxon_ids = None
        for identification in identifications:
            if identification["user"]["id"] == obs["user"]["id"]:
                observer_taxon_id = identification["taxon"]["id"]
                LOG.info("found an ID by user: taxon_id = %d", observer_taxon_id)
                observer_taxon_ids = identification["taxon"]["ancestor_ids"]
                observer_taxon_ids.append(observer_taxon_id)
        if observer_taxon_id:
            LOG.info("final ID by user: taxon_id = %d", observer_taxon_id)
            LOG.info("ident_taxon_ids = %s", repr(ident_taxon_ids))
            if observer_taxon_id in ident_taxon_ids:
                LOG.info("user's taxon and ancestors are: %s", repr(observer_taxon_ids))
                if obs_taxon["id"] in observer_taxon_ids:
                    LOG.info("user's ID was counted towards ID")
                    # Count as ident & agree:
                    idents_count += 1
                    idents_agree += 1
            else:
                LOG.info("user's ID was a maverick; counted against ID")
                # Count as maverick
                idents_count += 1
    faves = obs.get("faves_count")

    photos = obs.get("photos")
    if photos:
        thumbnail = photos[0].get("url")
    else:
        thumbnail = None

    return Obs(
        taxon,
        obs_id,
        obs_on,
        obs_at,
        user,
        thumbnail,
        quality_grade,
        idents_agree,
        idents_count,
        faves,
    )
