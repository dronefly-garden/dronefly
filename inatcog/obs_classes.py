"""Module providing observation classes & constants."""

import re
from typing import List, NamedTuple
from .api_classes import WWW_URL_PAT
from .photos import Photo
from .sounds import Sound
from .taxon_classes import Taxon
from .users import User

# Match observation URL or command.
PAT_OBS_LINK = re.compile(
    r"\b("
    r"(?P<url>" + WWW_URL_PAT + r"/observations/(?P<obs_id>\d+))"
    r"|(?P<cmd>obs\s+(?P<cmd_obs_id>\d+))"
    r")\b",
    re.I,
)
# Match observation URL from `obs` embed generated for observations matching a
# specific taxon_id and filtered by optional place_id and/or user_id.
PAT_OBS_TAXON_LINK = re.compile(
    r"\b(?P<url>" + WWW_URL_PAT + r"/observations"
    r"\?taxon_id=(?P<taxon_id>\d+)(&place_id=(?P<place_id>\d+))?(&user_id=(?P<user_id>\d+))?)\b",
    re.I,
)


class Obs(NamedTuple):
    """An observation."""

    taxon: Taxon or None
    community_taxon: Taxon or None
    obs_id: int
    obs_on: str
    obs_at: str
    user: User
    thumbnail: str
    images: List[Photo]
    quality_grade: str
    idents_agree: int
    idents_count: int
    faves_count: int
    comments_count: int
    description: str
    project_ids: list
    sounds: List[Sound]
