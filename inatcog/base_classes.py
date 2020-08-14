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

    main: SimpleQuery
    ancestor: SimpleQuery
    user: str
    place: str
    controlled_term: str


# TODO: this should just be Place, as it is a superset
@dataclass
class MeansPlace(DataClassJsonMixin):
    """The place for establishment means."""

    id: int
    name: str
    display_name: str
    ancestor_place_ids: List[int]


@dataclass
class PlacePartial(DataClassJsonMixin):
    """Minimal place info."""

    id: int
    display_name: str = None


@dataclass
class Checklist(DataClassJsonMixin):
    """A checklist."""

    id: int
    title: str


MEANS_LABEL_DESC = {
    "endemic": "endemic to",
    "native": "native in",
    "introduced": "introduced to",
}

MEANS_LABEL_EMOJI = {
    "endemic": ":star:",
    "native": ":eight_spoked_asterisk:",
    "introduced": ":arrow_up_small:",
}


@dataclass
class EstablishmentMeansPartial(DataClassJsonMixin):
    """Partial establishment means for a taxon in a place.

    This form is used for establishment_means as returned
    on a query with preferred_place_id set.
    """

    id: int
    establishment_means: str
    place: PlacePartial

    def url(self):
        """Partial establishment means listed taxon url."""
        return f"{WWW_BASE_URL}/listed_taxa/{self.id}"

    def list_link(self):
        """Partial establishment means listed taxon link in Markdown format."""
        return f"[Checklist]({self.url()})"

    def description(self):
        """Partial establishment means listed taxon url."""
        desc = MEANS_LABEL_DESC.get(self.establishment_means)
        if desc:
            return f"{desc} {self.place.display_name}"
        else:
            return (
                f"Establishment means {self.establishment_means} in "
                f"{self.place.display_name}"
            )

    def emoji(self):
        """Partial establishment means listed taxon emoji."""
        try:
            emoji = MEANS_LABEL_EMOJI[self.establishment_means] + "\u202f"
        except KeyError:
            emoji = ""
        return emoji

    def link(self):
        """Partial establishment means listed taxon url."""
        return f"[{self.description()}]({self.url()})"


@dataclass
class EstablishmentMeans(DataClassJsonMixin):
    """The establishment means for a taxon in a place."""

    id: int
    taxon_id: int
    establishment_means: str
    place: MeansPlace
    list: Checklist

    def url(self):
        """Establishment means listed taxon url."""
        return f"{WWW_BASE_URL}/listed_taxa/{self.id}"

    def list_link(self):
        """Establishment means listed taxon link in Markdown format."""
        return f"[{self.list.title}]({self.url()})"

    def description(self):
        """Establishment means description."""
        desc = MEANS_LABEL_DESC.get(self.establishment_means)
        if desc:
            return f"{desc} {self.place.display_name}"
        else:
            return (
                f"Establishment means {self.establishment_means} in "
                f"{self.place.display_name}"
            )

    def emoji(self):
        """Establishment means listed taxon emoji."""
        try:
            emoji = MEANS_LABEL_EMOJI[self.establishment_means] + "\u202f"
        except KeyError:
            emoji = ""
        return emoji

    def link(self):
        """Establishment means listed taxon url."""
        return f"[{self.description()}]({self.url()})"


@dataclass
class ListedTaxon(DataClassJsonMixin):
    """Listed taxon for an observation."""

    id: int
    establishment_means: str
    list_id: int
    taxon_id: int
    place: Optional[PlacePartial] = None

    def description(self):
        """Listed taxon description."""
        desc = MEANS_LABEL_DESC.get(self.establishment_means)
        if desc:
            return f"{desc} {self.place.display_name}"
        else:
            return (
                f"Establishment means {self.establishment_means} in "
                f"{self.place.display_name}"
            )

    def emoji(self):
        """Listed taxon emoji."""
        try:
            emoji = MEANS_LABEL_EMOJI[self.establishment_means] + "\u202f"
        except KeyError:
            emoji = ""
        return emoji

    def link(self):
        """Listed taxon link."""
        return f"[{self.description()}]({self.url()})"

    def url(self):
        """Listed taxon url."""
        return f"{WWW_BASE_URL}/listed_taxa/{self.id}"


@dataclass
class ConservationStatus(DataClassJsonMixin):
    """Conservation status for an observation."""

    authority: str
    status: str
    url: Optional[str] = ""
    place: Optional[PlacePartial] = None
    status_name: Optional[str] = ""

    def status_description(self):
        """Return a reasonable description of status giving various possible inputs."""
        if self.status.lower() in ("extinct", "ex"):
            return "extinct"
        if self.status_name:
            return f"{self.status_name} ({self.status.upper()})"
        return self.status.upper()

    def description(self):
        """Description of conservation status."""
        if self.place:
            return f"{self.status_description()} in {self.place.display_name}"
        return self.status_description()

    def link(self):
        """Link to conservation status authority."""
        if self.url:
            return f"[{self.authority}]({self.url})"
        return self.authority


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
    listed_taxa: list
    establishment_means: Optional[EstablishmentMeansPartial]
    conservation_status: Optional[ConservationStatus]


@dataclass
class TaxonSummary(DataClassJsonMixin):
    """Taxon summary for an observation."""

    conservation_status: Optional[ConservationStatus] = None
    listed_taxon: Optional[ListedTaxon] = None
    # Not currently in use:
    # wikipedia_summary: str = ""


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
    ancestor_place_ids: List[int]

    def __post_init__(self):
        """URL for place."""
        self.url = f"{WWW_BASE_URL}/places/{self.place_id}"


class FilteredTaxon(NamedTuple):
    """A taxon with optional filters."""

    taxon: Taxon
    user: User
    place: Place


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
