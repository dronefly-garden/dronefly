"""Module for base classes and constants."""
import datetime as dt
from typing import List, NamedTuple

from pyinaturalist.models import Taxon, User

from .photos import Photo
from .sounds import Sound

COG_NAME = "iNat"
WWW_BASE_URL = "https://www.inaturalist.org"


class Obs(NamedTuple):
    """An observation."""

    taxon: Taxon or None
    community_taxon: Taxon or None
    obs_id: int
    obs_on: dt.datetime
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
    time_obs: dt.datetime
