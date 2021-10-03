"""Module for base classes and constants."""
from dataclasses import dataclass, field
import datetime as dt
import re
from typing import List, NamedTuple, Optional, Union

from dataclasses_json import config, DataClassJsonMixin
from discord.utils import escape_markdown

from .controlled_terms import ControlledTermSelector
from .core import models
from .core.models.taxon import RANK_LEVELS, TAXON_PRIMARY_RANKS, TRINOMIAL_ABBR
from .photos import Photo
from .sounds import Sound

WWW_BASE_URL = "https://www.inaturalist.org"


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
        status_lowered = self.status.lower()
        # Avoid cases where showing both the name and code
        # adds no new information, e.g.
        # - "extinct (EXTINCT)" and "threatened (THREATENED)"
        # - return "extinct" or "threatened" instead
        if status_lowered == self.status_name.lower():
            return status_lowered
        if self.status_name:
            return f"{self.status_name} ({self.status.upper()})"
        # Avoid "shouting" status codes when no name is given and
        # they are long (i.e. they're probably names, not actual
        # status codes)
        # - e.g. "EXTINCT" or "THREATENED"
        if len(self.status) > 6:
            return self.status.lower()
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
class _TaxonBase(models.taxon.TaxonBase):
    """Base class for standard fields of cog Taxon."""


@dataclass
class _TaxonDefaultsBase(models.taxon.TaxonDefaultsBase):
    """Base class for optional fields of cog Taxon."""

    establishment_means: Optional[EstablishmentMeansPartial] = None
    conservation_status: Optional[ConservationStatus] = None


@dataclass
class Taxon(models.taxon.Taxon, _TaxonDefaultsBase, _TaxonBase):
    """Public class for taxon with cog-specific behaviours."""

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
                    self.matched_term
                    if self.matched_term not in (self.name, self.preferred_common_name)
                    else self.preferred_common_name
                )
            else:
                if hierarchy:
                    common = None
                else:
                    common = self.preferred_common_name
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
        if not self.is_active:
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
        if self.name:
            return f"{escape_markdown(self.name)} ({escape_markdown(self.login)})"
        return escape_markdown(self.login)

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
class DateSelector:
    """A date selector object."""

    # pylint: disable=invalid-name

    d1: Optional[Union[dt.datetime, str]]
    d2: Optional[Union[dt.datetime, str]]
    on: Optional[Union[dt.datetime, str]]


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
    observed: Optional[DateSelector]
    added: Optional[DateSelector]

    def obs_args(self):
        """Arguments for an observations query."""

        kwargs = _Params({"verifiable": "true"})
        kwargs.set_from(self.taxon, "id", "taxon_id")
        kwargs.set_from(self.user, "user_id")
        kwargs.set_from(self.project, "project_id")
        kwargs.set_from(self.place, "place_id")
        kwargs.set_from(self.id_by, "user_id", "ident_user_id")
        kwargs.set_from(self.unobserved_by, "user_id", "unobserved_by_user_id")
        if self.unobserved_by:
            kwargs["lrank"] = "species"
        if self.controlled_term:
            kwargs["term_id"] = self.controlled_term.term.id
            kwargs["term_value_id"] = self.controlled_term.value.id
        # In three cases, we need to allow verifiable=any:
        # 1. when a project is given, let the project rules sort it out, otherwise
        #    we interfere with searching for observations in projects that allow
        #    unverifiable observations
        # 2. when a user is given, which is like pressing "View All" on a taxon
        #    page, we want to match that feature on the website, i.e. users will
        #    be confused if they asked for their observations and none were given
        #    even though they know they have some
        # 3. same with 'id by' and for the same reason as =any for user
        #
        # - 'not by' is not the same. It's the target species a user will
        #   be looking for and it is undesirable to include unverifiable observations.
        # - if these defaults don't work for corner cases, they can be
        #   overridden in the query with: opt verifiable=<value> (i.e.
        #   self.options overrides are applied below)
        if (
            kwargs.get("project_id")
            or kwargs.get("user_id")
            or kwargs.get("ident_user_id")
        ):
            kwargs["verifiable"] = "any"
        if self.options:
            kwargs = {**kwargs, **self.options}
        if self.observed:
            if self.observed.on:
                kwargs["observed_on"] = str(self.observed.on.date())
            else:
                if self.observed.d1:
                    kwargs["d1"] = str(self.observed.d1.date())
                if self.observed.d2:
                    kwargs["d2"] = str(self.observed.d2.date())
        if self.added:
            if self.added.on:
                kwargs["created_on"] = str(self.added.on.date())
            else:
                if self.added.d1:
                    kwargs["created_d1"] = self.added.d1.isoformat()
                if self.added.d2:
                    kwargs["created_d2"] = self.added.d2.isoformat()
        return kwargs

    def obs_query_description(self):
        """Description of an observations query."""

        def _format_date(date: str):
            return date.strftime("%b %-d, %Y")

        def _format_time(time: str):
            return time.strftime("%b %-d, %Y %h:%m %p")

        message = ""
        if self.taxon:
            taxon = self.taxon
            message += " of " + taxon.format_name(with_term=True)
        if self.options:
            without_taxon_id = self.options.get("without_taxon_id")
            iconic_taxa = self.options.get("iconic_taxa")
            if iconic_taxa == "unknown":
                message += " of Unknown"
            else:
                taxon_ids = self.options.get("taxon_ids")
                # Note: if taxon_ids is given with "of" clause (taxon_id), then
                # taxon_ids is simply ignored, so we don't handle that case here.
                if taxon_ids and not self.taxon:
                    if taxon_ids == "20978,26036":
                        message += " of Amphibia, Reptilia (Herps)"
                    elif (
                        taxon_ids
                        == "152028,791197,54743,152030,175541,127378,117881,117869"
                    ):
                        message += (
                            " of Arthoniomycetes, Coniocybomycetes, Lecanoromycetes,"
                            " Lichinomycetes, Multiclavula, Mycocaliciales, Pyrenulales,"
                            "Verrucariales (Lichenized Fungi)"
                        )
                    else:
                        message += " of taxon #" + taxon_ids.replace(",", ", ")
                if without_taxon_id:
                    message += " without "
                    # TODO: support generally; hardwired cases are for waspsonly & mothsonly
                    if without_taxon_id == "47336,630955":
                        message += "Formicidae, Anthophila"
                    elif without_taxon_id == "47224":
                        message += "Papilionoidea"
                    elif without_taxon_id == "352459":
                        message += "Stictis radiata"
                    else:
                        message += "taxon #" + without_taxon_id.replace(",", ", ")
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
        if self.observed and self.observed.on or self.observed.d1 or self.observed.d2:
            message += " observed "
            if self.observed.on:
                message += f" on {_format_date(self.observed.on)}"
            else:
                if self.observed.d1:
                    message += f" on or after {_format_date(self.observed.d1)}"
                if self.observed.d2:
                    if self.observed.d1:
                        message += " and "
                    message += f" on or before {_format_date(self.observed.d2)}"
        if self.added and self.added.on or self.added.d1 or self.added.d2:
            message += " added "
            if self.added.on:
                message += f" on {_format_date(self.observed.on)}"
            else:
                if self.added.d1:
                    message += f" on or after {_format_time(self.added.d1)}"
                if self.added.d2:
                    if self.added.d1:
                        message += " and "
                    message += f" on or before {_format_time(self.added.d2)}"
        if self.controlled_term:
            (term, term_value) = self.controlled_term
            desc = f" with {term.label}"
            desc += f" {term_value.label}"
            message += desc
        kwargs = self.obs_args()
        hrank = kwargs.get("hrank")
        lrank = kwargs.get("lrank")
        if lrank or hrank:
            with_or_and = "with" if not self.controlled_term else "and"
            if lrank and hrank:
                message += " {} rank from {} through {}".format(
                    with_or_and, lrank, hrank
                )
            else:
                higher_or_lower = "higher" if lrank else "lower"
                message += " {} rank {} or {}".format(
                    with_or_and, hrank or lrank, higher_or_lower
                )
        return re.sub(r"^ ", "", message)


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
