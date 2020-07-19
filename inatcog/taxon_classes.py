"""Module containing taxon query classes."""
from typing import List, NamedTuple, Optional
from .places import Place
from .users import User


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


class FilteredTaxon(NamedTuple):
    """A taxon with optional filters."""

    taxon: Taxon
    user: User
    place: Place
    group_by: str
    # location: Location
