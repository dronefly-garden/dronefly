"""Module for base classes and constants."""
from dataclasses import dataclass, field
import datetime as dt
import re
from typing import List, NamedTuple, Optional, Union

from dataclasses_json import config, DataClassJsonMixin
from discord.utils import escape_markdown
from dronefly.core.formatters.generic import format_taxon_name
from dronefly.core.models.taxon import Taxon

from .controlled_terms import ControlledTermSelector
from .photos import Photo
from .sounds import Sound

COG_NAME = "iNat"
WWW_BASE_URL = "https://www.inaturalist.org"


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
    description: str
    icon: str
    banner_color: str

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
    except_by: Optional[User]
    id_by: Optional[User]
    project: Optional[Project]
    options: Optional[dict]
    controlled_term: Optional[ControlledTermSelector]
    observed: Optional[DateSelector]
    added: Optional[DateSelector]
    adjectives: Optional[List[str]] = field(init=False)

    def __post_init__(self):
        adjectives = []
        if self.options:
            quality_grade = (self.options.get("quality_grade") or "").split(",")
            verifiable = self.options.get("verifiable")
            if "any" not in quality_grade:
                research = "research" in quality_grade
                needsid = "needs_id" in quality_grade
            # If specified, will override any quality_grade set already:
            if verifiable:
                if verifiable in ["true", ""]:
                    research = True
                    needsid = True
            if verifiable == "false":
                adjectives.append("*not Verifiable*")
            elif research and needsid:
                adjectives.append("*Verifiable*")
            else:
                if research:
                    adjectives.append("*Research Grade*")
                if needsid:
                    adjectives.append("*Needs ID*")
        self.adjectives = adjectives

    def obs_args(self):
        """Arguments for an observations query."""

        kwargs = _Params({"verifiable": "true"})
        kwargs.set_from(self.taxon, "id", "taxon_id")
        kwargs.set_from(self.user, "user_id")
        kwargs.set_from(self.project, "project_id")
        kwargs.set_from(self.place, "place_id")
        kwargs.set_from(self.id_by, "user_id", "ident_user_id")
        kwargs.set_from(self.unobserved_by, "user_id", "unobserved_by_user_id")
        kwargs.set_from(self.except_by, "user_id", "not_user_id")
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

    def obs_query_description(self, with_adjectives: bool = True):
        """Description of an observations query."""

        def _format_date(date: str):
            return date.strftime("%b %-d, %Y")

        def _format_time(time: str):
            return time.strftime("%b %-d, %Y %h:%m %p")

        message = ""
        of_taxa_description = ""
        without_taxa_description = ""
        if self.taxon:
            taxon = self.taxon
            of_taxa_description = format_taxon_name(taxon, with_term=True)
        if self.options:
            without_taxon_id = self.options.get("without_taxon_id")
            iconic_taxa = self.options.get("iconic_taxa")
            if iconic_taxa == "unknown":
                of_taxa_description = "Unknown"
            else:
                taxon_ids = self.options.get("taxon_ids")
                # Note: if taxon_ids is given with "of" clause (taxon_id), then
                # taxon_ids is simply ignored, so we don't handle that case here.
                if taxon_ids and not self.taxon:
                    # TODO: support generally; hardwired cases here are for herps,
                    # lichenish, and seaslugs
                    of_taxa_description = {
                        "20978,26036": "Amphibia, Reptilia (Herps)",
                        # Note: the list is getting a bit ridiculously long - maybe
                        # just call this grouping "Probably lichens"?
                        "152028,791197,54743,152030,175541,127378,117881,117869": (
                            "Arthoniomycetes, Coniocybomycetes, Lecanoromycetes,"
                            " Lichinomycetes, Multiclavula, Mycocaliciales, Pyrenulales,"
                            "Verrucariales (Lichenized Fungi)"
                        ),
                        "130687,775798,775804,49784,500752,47113,775801,775833,775805,495793,47801,801507": (
                            "Nudibranchia, Aplysiida, etc. (Nudibranchs, Sea Hares, "
                            "other marine slugs)"
                        ),
                    }.get(taxon_ids) or "taxon #" + taxon_ids.replace(",", ", ")
                if without_taxon_id:
                    # TODO: support generally; hardwired cases here are for
                    # waspsonly, mothsonly, lichenish, etc.
                    without_taxa_description = {
                        "47336,630955": "Formicidae, Anthophila",
                        "47224": "Papilionoidea",
                        "352459": "Stictis radiata",
                        "47125": "Angiospermae",
                        "211194": "Tracheophyta",
                        "355675": "Vertebrata",
                    }.get(without_taxon_id) or "taxon #" + without_taxon_id.replace(
                        ",", ", "
                    )

        _taxa_description = []
        if of_taxa_description:
            _of = ["of"]
            if with_adjectives and self.adjectives:
                _of.append(", ".join(self.adjectives))
            _of.append(of_taxa_description)
            _taxa_description.append(" ".join(_of))
        if without_taxa_description:
            _without = []
            # If we only have "without" =>
            #   "of [adjectives] taxa without [taxa]":
            if not of_taxa_description and with_adjectives:
                _without.append("of")
                if with_adjectives and self.adjectives:
                    _without.append(", ".join(self.adjectives))
                _without.append("taxa")
            _without.append("without")
            _without.append(without_taxa_description)
            _taxa_description.append(" ".join(_without))
        if with_adjectives and not _taxa_description:
            _of = ["of"]
            if with_adjectives and self.adjectives:
                _of.append(", ".join(self.adjectives))
            _of.append("taxa")
            _taxa_description.append(" ".join(_of))
        message += " ".join(_taxa_description)
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
        if self.except_by:
            message += " except by " + self.except_by.display_name()
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
