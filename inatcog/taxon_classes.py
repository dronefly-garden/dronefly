"""Module containing taxon query classes."""
from typing import List, NamedTuple


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
