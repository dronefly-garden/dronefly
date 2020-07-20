"""Module for base classes and constants."""
import re
from typing import List, NamedTuple, Optional
from dataclasses import dataclass, field
from dataclasses_json import config, DataClassJsonMixin
from .photos import Photo
from .sounds import Sound

API_BASE_URL = "https://api.inaturalist.org"
WWW_BASE_URL = "https://www.inaturalist.org"
# Match any iNaturalist partner URL
# See https://www.inaturalist.org/pages/network
WWW_URL_PAT = (
    r"https?://("
    r"((www|colombia|panama|ecuador|israel)\.)?inaturalist\.org"
    r"|inaturalist\.ala\.org\.au"
    r"|(www\.)?("
    r"inaturalist\.(ca|nz)"
    r"|naturalista\.mx"
    r"|biodiversity4all\.org"
    r"|argentinat\.org"
    r"|inaturalist\.laji\.fi"
    r")"
    r")"
)

# Match observation URL or command.
PAT_OBS_LINK = re.compile(
    r"\b(?P<url>" + WWW_URL_PAT + r"/observations/(?P<obs_id>\d+))\b", re.I
)
# Match observation URL from `obs` embed generated for observations matching a
# specific taxon_id and filtered by optional place_id and/or user_id.
PAT_OBS_TAXON_LINK = re.compile(
    r"\b(?P<url>" + WWW_URL_PAT + r"/observations"
    r"\?taxon_id=(?P<taxon_id>\d+)(&place_id=(?P<place_id>\d+))?(&user_id=(?P<user_id>\d+))?)\b",
    re.I,
)

# RANK_LEVELS and RANK_EQUIVALENTS are from:
# - https://github.com/inaturalist/inaturalist/blob/master/app/models/taxon.rb
RANK_LEVELS = {
    "stateofmatter": 100,
    "unranked": 90,  # Invented to make parent check work (this is null in the db)
    "kingdom": 70,
    "phylum": 60,
    "subphylum": 57,
    "superclass": 53,
    "class": 50,
    "subclass": 47,
    "infraclass": 45,
    "subterclass": 44,
    "superorder": 43,
    "order": 40,
    "suborder": 37,
    "infraorder": 35,
    "parvorder": 34.5,
    "zoosection": 34,
    "zoosubsection": 33.5,
    "superfamily": 33,
    "epifamily": 32,
    "family": 30,
    "subfamily": 27,
    "supertribe": 26,
    "tribe": 25,
    "subtribe": 24,
    "genus": 20,
    "genushybrid": 20,
    "subgenus": 15,
    "section": 13,
    "subsection": 12,
    "complex": 11,
    "species": 10,
    "hybrid": 10,
    "subspecies": 5,
    "variety": 5,
    "form": 5,
    "infrahybrid": 5,
}

RANK_EQUIVALENTS = {
    "division": "phylum",
    "sub-class": "subclass",
    "super-order": "superorder",
    "sub-order": "suborder",
    "super-family": "superfamily",
    "sub-family": "subfamily",
    "gen": "genus",
    "sp": "species",
    "spp": "species",
    "infraspecies": "subspecies",
    "ssp": "subspecies",
    "sub-species": "subspecies",
    "subsp": "subspecies",
    "trinomial": "subspecies",
    "var": "variety",
    # 'unranked': None,
}

RANK_KEYWORDS = tuple(RANK_LEVELS.keys()) + tuple(RANK_EQUIVALENTS.keys())


class SimpleQuery(NamedTuple):
    """A taxon query composed of terms and/or phrases or a code or taxon_id, filtered by ranks."""

    taxon_id: int
    terms: List[str]
    phrases: List[str]
    ranks: List[str]
    code: str


class CompoundQuery(NamedTuple):
    """A taxon query that may contain another (ancestor) taxon query."""

    main: str
    ancestor: str
    user: str
    place: str
    group_by: str
    controlled_term: str


class Taxon(NamedTuple):
    """A taxon."""

    name: str
    taxon_id: int
    common: Optional[str]
    term: str
    thumbnail: Optional[str]
    image: Optional[str]
    image_attribution: Optional[str]
    rank: str
    ancestor_ids: list
    observations: int
    ancestor_ranks: list
    active: bool


@dataclass
class User(DataClassJsonMixin):
    """A user."""

    user_id: int = field(metadata=config(field_name="id"))
    name: Optional[str]
    login: str
    observations_count: int
    identifications_count: int

    def display_name(self):
        """Name to include in displays."""
        return f"{self.name} ({self.login})" if self.name else self.login

    def profile_url(self):
        """User profile url."""
        return f"{WWW_BASE_URL}/people/{self.login}" if self.login else ""

    def profile_link(self):
        """User profile link in markdown format."""
        return f"[{self.display_name()}]({self.profile_url()})"


@dataclass
class Place(DataClassJsonMixin):
    """An iNat place."""

    display_name: str
    place_id: int = field(metadata=config(field_name="id"))
    url: str = field(init=False)

    def __post_init__(self):
        """URL for place."""
        self.url = f"{WWW_BASE_URL}/places/{self.place_id}"


class FilteredTaxon(NamedTuple):
    """A taxon with optional filters."""

    taxon: Taxon
    user: User
    place: Place
    group_by: str
    # location: Location


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
