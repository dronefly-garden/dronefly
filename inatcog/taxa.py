"""Module to work with iNat taxa."""
import copy
import re
from typing import NamedTuple, Optional, Union
from urllib.parse import urlencode

from .base_classes import (
    ConservationStatus,
    EstablishmentMeans,
    EstablishmentMeansPartial,
    Taxon,
    User,
    Place,
    WWW_BASE_URL,
)
from .common import LOG
from .core.models.taxon import RANK_LEVELS
from .core.parsers.url import STATIC_URL_PAT
from .core.query.query import TaxonQuery


TAXON_ID_LIFE = 48460
TAXON_PLACES_HEADER = "__obs# (spp#) from place:__"
TAXON_PLACES_HEADER_PAT = re.compile(re.escape(TAXON_PLACES_HEADER) + "\n")
TAXON_COUNTS_HEADER = "__obs# (spp#) by user:__"
TAXON_COUNTS_HEADER_PAT = re.compile(re.escape(TAXON_COUNTS_HEADER) + "\n")
TAXON_IDBY_HEADER = "__obs# (spp#) identified by user:__"
TAXON_IDBY_HEADER_PAT = re.compile(re.escape(TAXON_IDBY_HEADER) + "\n")
TAXON_NOTBY_HEADER = "__obs# (spp#) unobserved by user:__"
TAXON_NOTBY_HEADER_PAT = re.compile(re.escape(TAXON_NOTBY_HEADER) + "\n")
TAXON_LIST_DELIMITER = [", ", " > "]


def format_taxon_names(
    taxa, with_term=False, names_format="%s", max_len=0, hierarchy=False
):
    """Format names of taxa from matched records.

    Parameters
    ----------
    rec: Taxon
        A matched taxon record.
    with_term: bool, optional
        With non-common / non-name matching term in parentheses in place of common name.
    names_format: str, optional
        Format string for the name. Must contain exactly one %s.
    max_len: int, optional
        The maximum length of the return str, with ', and # more' appended if they
        don't all fit within this length.
    hierarchy: bool, optional
        If specified, formats a hierarchy list of scientific names with
        primary ranks bolded & starting on a new line, and delimited with
        angle-brackets instead of commas.

    Returns
    -------
    str
        A delimited list of formatted taxon names.
    """

    delimiter = TAXON_LIST_DELIMITER[int(hierarchy)]

    names = [
        taxon.format_name(with_term=with_term, hierarchy=hierarchy) for taxon in taxa
    ]

    def fit_names(names):
        names_fit = []
        # Account for space already used by format string (minus 2 for %s)
        available_len = max_len - (len(names_format) - 2)

        def more(count):
            return "and %d more" % count

        def formatted_len(name):
            return sum(len(item) + len(delimiter) for item in names_fit) + len(name)

        def overflow(name):
            return formatted_len(name) > available_len

        for name in names:
            if overflow(name):
                unprocessed = len(names) - len(names_fit)
                while overflow(more(unprocessed)):
                    unprocessed += 1
                    del names_fit[-1]
                names_fit.append(more(unprocessed))
                break
            else:
                names_fit.append(name)
        return names_fit

    if max_len:
        names = fit_names(names)

    return names_format % delimiter.join(names)


async def get_taxon_preferred_establishment_means(bot, ctx, taxon):
    """Get the preferred establishment means for the taxon."""
    try:
        establishment_means = taxon.establishment_means
        place_id = establishment_means.place.id
        home = await bot.get_home(ctx)
        full_taxon = (
            taxon
            if taxon.listed_taxa
            else await get_taxon(bot, taxon.id, preferred_place_id=int(home))
        )
    except (AttributeError, LookupError):
        return None

    find_means = (
        means for means in full_taxon.listed_taxa if means.place.id == place_id
    )
    return next(find_means, establishment_means)


def get_taxon_fields(record):
    """Get Taxon from a JSON record.

    Parameters
    ----------
    record: dict
        The JSON record from /v1/taxa or /v1/taxa/autocomplete.

    Returns
    -------
    Taxon
        A Taxon object from the JSON record.
    """

    def make_means(means):
        try:
            return EstablishmentMeans.from_dict(means)
        except KeyError:
            pass

    def make_means_partial(means):
        try:
            return EstablishmentMeansPartial.from_dict(means)
        except KeyError:
            pass

    thumbnail = None
    photo = record.get("default_photo")
    if photo:
        thumbnail = photo.get("square_url")
        # Though default_photo only contains small versions of the image,
        # the original can be obtained for self-hosted images via this
        # transform on the thumbnail image:
        if re.search(STATIC_URL_PAT, thumbnail):
            image = re.sub("/square", "/original", thumbnail)
            attribution = photo.get("attribution")
        else:
            # For externally hosted default images (e.g. Flickr), only full records
            # retrieved via id# contain taxon_photos.
            # - See make_image_embed (inat_embeds.py) which does the extra API call
            #   to fetch the full-quality photo.
            taxon_photos = record.get("taxon_photos")
            if taxon_photos:
                image = taxon_photos[0]["photo"]["original_url"]
                attribution = taxon_photos[0]["photo"]["attribution"]
            else:
                image = None
                attribution = None
    else:
        thumbnail = None
        image = None
        attribution = None
    taxon_id = record["id"] if "id" in record else record["taxon_id"]
    ancestors = record.get("ancestors") or []
    ancestor_ranks = (
        ["stateofmatter"] + [ancestor["rank"] for ancestor in ancestors]
        if ancestors
        else []
    )
    listed_taxa_raw = record.get("listed_taxa")
    if listed_taxa_raw:
        listed_taxa = [make_means(means) for means in listed_taxa_raw]
    else:
        listed_taxa = []
    establishment_means_raw = record.get("establishment_means")
    if establishment_means_raw:
        establishment_means = make_means_partial(establishment_means_raw)
    else:
        establishment_means = None
    conservation_status_raw = record.get("conservation_status")
    if conservation_status_raw:
        LOG.info(conservation_status_raw)
        conservation_status = ConservationStatus.from_dict(conservation_status_raw)
    else:
        conservation_status = None
    preferred_common_name = record.get("preferred_common_name")
    taxon = Taxon(
        name=record["name"],
        id=taxon_id,
        matched_term=record.get("matched_term") or preferred_common_name,
        rank=record["rank"],
        ancestor_ids=record["ancestor_ids"],
        observations_count=record["observations_count"],
        ancestor_ranks=ancestor_ranks,
        is_active=record["is_active"],
        listed_taxa=listed_taxa,
        names=record.get("names"),
        preferred_common_name=preferred_common_name,
        thumbnail=thumbnail,
        image=image,
        image_attribution=attribution,
        establishment_means=establishment_means,
        conservation_status=conservation_status,
    )
    return taxon


class NameMatch(NamedTuple):
    """Match for each name field in Taxon matching a pattern."""

    term: Optional[re.match]
    name: Optional[re.match]
    common: Optional[re.match]


NO_NAME_MATCH = NameMatch(None, None, None)


def match_pat(record, pat, scientific_name=False, locale=None):
    """Match specified pattern.

    Parameters
    ----------
    record: Taxon
        A candidate taxon to match.

    pat: re.Pattern or str
        A pattern to match against each name field in the record.

    scientific_name: bool
        Only search scientific name

    locale: str
        Only search common names matching locale

    Returns
    -------
    NameMatch
        A tuple of search results for the pat for each name in the record.
    """
    if scientific_name:
        return NameMatch(
            None,
            re.search(pat, record.name),
            None,
        )
    if locale:
        names = [
            name["name"]
            for name in sorted(
                [
                    name
                    for name in record.names
                    if name["is_valid"] and re.match(locale, name["locale"], re.I)
                ],
                key=lambda x: x["position"],
            )
        ]
        for name in names:
            mat = re.search(pat, name)
            if mat:
                LOG.info("match=%s", pat)
                return NameMatch(
                    mat,
                    None,
                    mat,
                )
        return NO_NAME_MATCH
    return NameMatch(
        re.search(pat, record.matched_term),
        re.search(pat, record.name),
        re.search(pat, record.preferred_common_name)
        if record.preferred_common_name
        else None,
    )


def match_pat_list(record, pat_list, scientific_name=False, locale=None):
    """Match all of a list of patterns.

    Parameters
    ----------
    record: Taxon
        A candidate taxon to match.

    exact: list
        A list of patterns to match.

    Returns
    -------
    NameMatch
        A tuple of ORed search results for every pat for each name in
        the record, i.e. each name in the tuple is the match result from
        the first matching pattern.
    """
    matched = NO_NAME_MATCH
    try:
        for pat in pat_list:
            this_match = match_pat(record, pat, scientific_name, locale)
            if this_match == NO_NAME_MATCH:
                matched = this_match
                raise ValueError("At least one field must match.")
            matched = NameMatch(
                matched.term or this_match.term,
                matched.name or this_match.name,
                matched.common or this_match.common,
            )
    except ValueError:
        pass

    return matched


def score_match(
    taxon_query: TaxonQuery,
    record,
    all_terms,
    pat_list=None,
    scientific_name=False,
    locale=None,
):
    """Score a matched record. A higher score is a better match.
    Parameters
    ----------
    taxon_query: TaxonQuery
        The query for the matched record being scored.

    record: Taxon
        A candidate taxon to match.

    all_terms: re.Pattern
        A pattern matching all terms.

    pat_list: list
        A list of patterns to match.

    Returns
    -------
    int
        score < 0 indicates the match is not a valid candidate.
        score >= 0 and score < 200 indicates a non-exact match
        score >= 200 indicates an exact match either on a phrase or the whole query
    """
    score = 0

    if taxon_query.taxon_id:
        return 1000  # An id is always the best match

    matched = (
        match_pat_list(record, pat_list, scientific_name, locale)
        if pat_list
        else NO_NAME_MATCH
    )
    all_matched = (
        match_pat(record, all_terms, scientific_name, locale)
        if taxon_query.taxon_id
        else NO_NAME_MATCH
    )

    if scientific_name:
        if matched.name:
            score = 200
        else:
            score = -1
    elif locale:
        if matched.term:
            score = 200
        else:
            score = -1
    else:
        if taxon_query.code and (taxon_query.code == record.matched_term):
            score = 300
        elif matched.name or matched.common:
            score = 210
        elif matched.term:
            score = 200
        elif all_matched.name or all_matched.common:
            score = 120
        elif all_matched.term:
            score = 110
        else:
            score = 100

    return score


def match_taxon(taxon_query: TaxonQuery, records, scientific_name=False, locale=None):
    """Match a single taxon for the given query among records returned by API."""
    pat_list = []
    all_terms = re.compile(r"^%s$" % re.escape(" ".join(taxon_query.terms)), re.I)
    if taxon_query.phrases:
        for phrase in taxon_query.phrases:
            pat = re.compile(r"\b%s\b" % re.escape(" ".join(phrase)), re.I)
            pat_list.append(pat)
    elif scientific_name or locale:
        for term in taxon_query.terms:
            pat = re.compile(r"\b%s" % re.escape(term), re.I)
            pat_list.append(pat)
    scores = [0] * len(records)

    for num, record in enumerate(records, start=0):
        scores[num] = score_match(
            taxon_query,
            record,
            all_terms=all_terms,
            pat_list=pat_list,
            scientific_name=scientific_name,
            locale=locale,
        )

    best_score = max(scores)
    best_record = records[scores.index(best_score)]
    min_score_met = (best_score >= 0) and (
        (not taxon_query.phrases) or (best_score >= 200)
    )

    return best_record if min_score_met else None


async def format_place_taxon_counts(
    cog,
    place: Union[Place, str],
    taxon: Taxon = None,
    **kwargs,
):
    """Format user observation & species counts for taxon."""
    if isinstance(place, str):
        name = "*total*"
    else:
        name = place.display_name
    obs_opt = copy.copy(kwargs)
    # TODO: Refactor. See same logic in obs_args in taxa.py and comment
    # explaining why we use verifiable=any in these cases.
    # - we don't have a QueryResponse here, but perhaps should
    #   synthesize one from the embed
    # - however, updating embeds is due to be rewritten soon, so it
    #   should probably be sorted out in the rewrite
    count_unverifiable_observations = (
        kwargs.get("project_id") or kwargs.get("user_id") or kwargs.get("ident_user_id")
    )
    if count_unverifiable_observations:
        obs_opt["verifiable"] = "any"
    observations = await cog.api.get_observations(per_page=0, **obs_opt)
    if observations:
        species = await cog.api.get_observations(
            "species_counts", per_page=0, **obs_opt
        )
        observations_count = observations["total_results"]
        species_count = species["total_results"]
        url = f"{WWW_BASE_URL}/observations?" + urlencode(obs_opt)
        if taxon and RANK_LEVELS[taxon.rank] <= RANK_LEVELS["species"]:
            link = f"[{observations_count:,}]({url}) {name}"
        else:
            link = f"[{observations_count:,} ({species_count:,})]({url}) {name}"
        return f"{link} "

    return ""


async def format_user_taxon_counts(
    cog,
    user: Union[User, str],
    taxon: Taxon = None,
    **kwargs,
):
    """Format user observation & species counts for taxon."""
    if isinstance(user, str):
        login = "*total*"
    else:
        login = user.login
    obs_opt = copy.copy(kwargs)
    # TODO: Refactor. See same logic in obs_args in taxa.py and comment
    # explaining why we use verifiable=any in these cases.
    # - we don't have a QueryResponse here, but perhaps should
    #   synthesize one from the embed
    # - however, updating embeds is due to be rewritten soon, so it
    #   should probably be sorted out in the rewrite
    count_unverifiable_observations = (
        kwargs.get("project_id") or kwargs.get("user_id") or kwargs.get("ident_user_id")
    )
    if count_unverifiable_observations:
        obs_opt["verifiable"] = "any"
    species_opt = copy.copy(obs_opt)
    if kwargs.get("unobserved_by_user_id"):
        obs_opt["lrank"] = "species"
    observations = await cog.api.get_observations(per_page=0, **obs_opt)
    if observations:
        species = await cog.api.get_observations(
            "species_counts", per_page=0, **species_opt
        )
        observations_count = observations["total_results"]
        species_count = species["total_results"]
        url = f"{WWW_BASE_URL}/observations?" + urlencode(obs_opt)
        if taxon and RANK_LEVELS[taxon.rank] <= RANK_LEVELS["species"]:
            link = f"[{observations_count:,}]({url}) {login}"
        else:
            link = f"[{observations_count:,} ({species_count:,})]({url}) {login}"
        return f"{link} "

    return ""


async def get_taxon(cog, taxon_id, **kwargs):
    """Get taxon by id."""
    results = (await cog.api.get_taxa(taxon_id, **kwargs))["results"]
    return get_taxon_fields(results[0]) if results else None
