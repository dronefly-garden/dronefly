"""Module for base classes and constants."""
import datetime as dt
import re
from typing import List, NamedTuple, Optional
from dataclasses import dataclass, field
from dataclasses_json import config, DataClassJsonMixin
from .controlled_terms import ControlledTermSelector
from .photos import Photo
from .sounds import Sound

API_BASE_URL = "https://api.inaturalist.org"
WWW_BASE_URL = "https://www.inaturalist.org"
# Match any iNaturalist partner URL
# See https://www.inaturalist.org/pages/network
WWW_URL_PAT = (
    r"https?://("
    r"((www|colombia|panama|ecuador|israel|greece|uk)\.)?inaturalist\.org"
    r"|inaturalist\.ala\.org\.au"
    r"|(www\.)?("
    r"inaturalist\.(ca|lu|nz)"
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

QUERY_PAT = r"\??(?:&?[^=&]*=[^=&]*)*"
PAT_OBS_QUERY = re.compile(
    r"(?P<url>" + WWW_URL_PAT + r"/observations" + QUERY_PAT + ")"
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
TAXON_PRIMARY_RANKS = ["kingdom", "phylum", "class", "order", "family"]
TRINOMIAL_ABBR = {"variety": "var.", "subspecies": "ssp.", "form": "f."}


class TaxonQuery(NamedTuple):
    """A taxon query composed of terms and/or phrases or a code or taxon_id, filtered by ranks."""

    taxon_id: int
    terms: List[str]
    phrases: List[str]
    ranks: List[str]
    code: str


@dataclass
class Query:
    """A taxon query that may contain another (ancestor) taxon query."""

    main: Optional[TaxonQuery] = None
    ancestor: Optional[TaxonQuery] = None
    user: Optional[str] = None
    place: Optional[str] = None
    controlled_term: Optional[str] = None
    unobserved_by: Optional[str] = None
    id_by: Optional[str] = None
    per: Optional[str] = None
    project: Optional[str] = None
    options: Optional[List] = None


EMPTY_QUERY = Query()


# TODO: this should just be Place, as it is a superset
@dataclass
class MeansPlace(DataClassJsonMixin):
    """The place for establishment means."""

    id: int
    name: str
    display_name: str


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
    "endemic": ":sparkle:",
    "native": ":green_square:",
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


@dataclass
class Taxon:
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
    names: list
    establishment_means: Optional[EstablishmentMeansPartial]
    conservation_status: Optional[ConservationStatus]

    def format_name(
        self, with_term=False, hierarchy=False, with_rank=True, with_common=True
    ):
        """Format taxon name.

        Parameters
        ----------
        with_term: bool, optional
            When with_common=True, non-common / non-name matching term is put in
            parentheses in place of common name.
        hierarchy: bool, optional
            If specified, produces a list item suitable for inclusion in the hierarchy section
            of a taxon embed. See format_taxon_names() for details.
        with_rank: bool, optional
            If specified and hierarchy=False, includes the rank for ranks higher than species.
        with_common: bool, optional
            If specified, include common name in parentheses after scientific name.

        Returns
        -------
        str
            A name of the form "Rank Scientific name (Common name)" following the
            same basic format as iNaturalist taxon pages on the web, i.e.

            - drop the "Rank" keyword for species level and lower
            - italicize the name (minus any rank abbreviations; see next point) for genus
            level and lower
            - for trinomials (must be subspecies level & have exactly 3 names to qualify),
            insert the appropriate abbreviation, unitalicized, between the 2nd and 3rd
            name (e.g. "Anser anser domesticus" -> "*Anser anser* var. *domesticus*")
        """

        if with_common:
            if with_term:
                common = (
                    self.term
                    if self.term not in (self.name, self.common)
                    else self.common
                )
            else:
                if hierarchy:
                    common = None
                else:
                    common = self.common
        else:
            common = None
        name = self.name

        rank = self.rank
        rank_level = RANK_LEVELS[rank]

        if rank_level <= RANK_LEVELS["genus"]:
            name = f"*{name}*"
        if rank_level > RANK_LEVELS["species"]:
            if hierarchy:
                bold = ("\n> **", "**") if rank in TAXON_PRIMARY_RANKS else ("", "")
                name = f"{bold[0]}{name}{bold[1]}"
            elif with_rank:
                name = f"{rank.capitalize()} {name}"
        else:
            if rank in TRINOMIAL_ABBR.keys():
                tri = name.split(" ")
                if len(tri) == 3:
                    # Note: name already italicized, so close/reopen italics around insertion.
                    name = f"{tri[0]} {tri[1]}* {TRINOMIAL_ABBR[rank]} *{tri[2]}"
        full_name = f"{name} ({common})" if common else name
        if not self.active:
            full_name += " :exclamation: Inactive Taxon"
        return full_name


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

    def __post_init__(self):
        """URL for place."""
        self.url = f"{WWW_BASE_URL}/places/{self.place_id}"


@dataclass
class Project(DataClassJsonMixin):
    """A project."""

    project_id: int = field(metadata=config(field_name="id"))
    title: str
    url: str = field(init=False)

    def __post_init__(self):
        """URL for project."""
        self.url = f"{WWW_BASE_URL}/projects/{self.project_id}"


class _Params(dict):
    def set_from(self, obj: object, attr_name: str, param_name: str = None):
        """Helper for simple one-to-one attribute to param assignments."""
        if obj:
            key = param_name or attr_name
            value = getattr(obj, attr_name)
            self[key] = value


@dataclass
class QueryResponse:
    """A generic query response object.

    - The parsed QueryResponse contains zero or more objects that are already
      each queried against the API and, optionally some additional options to
      apply to secondary entity queries. It is used in these main contexts:
      - Accessing the details of the primary entity object.
      - One or more queries for secondary entities related to the primary entity
        (e.g. observations).
    - For example, the command `,taxon rg bees by ben` transforms the query as follows:
      - `bees` is queried and parsed into a `Taxon` object for `/taxa/630955-Anthophila`
      - `ben`, in the context of a Discord server where this user is registered
        and is the best match, is parsed into a `User` object for `/people/benarmstrong`
        (which very likely can be fetched from cache)
      - `rg` is a macro for `"opt": {"quality_grade": "research"}`
      - The primary entity displayed by the `,taxon` command is `Anthophila`.
      - The secondary entities are observations & species counts of
        `Anthophila` for `benarmstrong` that are `research grade`, shown as a
        subdisplay.
    """

    taxon: Optional[Taxon]
    user: Optional[User]
    place: Optional[Place]
    unobserved_by: Optional[User]
    id_by: Optional[User]
    project: Optional[Project]
    options: Optional[dict]
    controlled_term: Optional[ControlledTermSelector]

    def obs_args(self):
        """Arguments for an observations query."""

        kwargs = _Params({"verifiable": "any"})
        kwargs.set_from(self.taxon, "taxon_id")
        kwargs.set_from(self.user, "user_id")
        kwargs.set_from(self.project, "project_id")
        kwargs.set_from(self.place, "place_id")
        kwargs.set_from(self.id_by, "user_id", "ident_user_id")
        kwargs.set_from(self.unobserved_by, "user_id", "unobserved_by_user_id")
        if self.unobserved_by:
            kwargs["lrank"] = "species"
        if self.controlled_term:
            kwargs["term_id"] = self.controlled_term.term.id
            kwargs["term_value_id"] = self.controlled_term.term_value.id
        if self.options:
            kwargs = {**kwargs, **self.options}
        return kwargs

    def obs_query_description(self):
        """Description of an observations query."""
        message = ""
        if self.taxon:
            taxon = self.taxon
            message += " of " + taxon.format_name(with_term=True)
        if self.project:
            message += " in " + self.project.title
        if self.place:
            message += " from " + self.place.display_name
        if self.user:
            message += " by " + self.user.display_name()
        if self.unobserved_by:
            message += " unobserved by " + self.unobserved_by.display_name()
        if self.id_by:
            message += " identified by " + self.id_by.display_name()
        if self.controlled_term:
            (term, term_value) = self.controlled_term
            desc = f" with {term.label}"
            desc += f" {term_value.label}"
            message += desc
        return message


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
