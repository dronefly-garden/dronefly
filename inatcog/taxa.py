"""Module to work with iNat taxa."""
import copy
import re
from typing import NamedTuple, Optional, Union

from dronefly.core.constants import RANK_LEVELS
from dronefly.core.query.query import TaxonQuery
from dronefly.core.utils import obs_url_from_v1
from pyinaturalist.models import Place, Taxon, User
from redbot.core.commands import Context


TAXON_PLACES_HEADER = "__obs# (spp#) from place:__"
TAXON_PLACES_HEADER_PAT = re.compile(re.escape(TAXON_PLACES_HEADER) + "\n")
TAXON_COUNTS_HEADER = "__obs# (spp#) by user:__"
TAXON_COUNTS_HEADER_PAT = re.compile(re.escape(TAXON_COUNTS_HEADER) + "\n")
TAXON_IDBY_HEADER = "__obs# (spp#) identified by user:__"
TAXON_IDBY_HEADER_PAT = re.compile(re.escape(TAXON_IDBY_HEADER) + "\n")
TAXON_NOTBY_HEADER = "__obs# (spp#) unobserved by user:__"
TAXON_NOTBY_HEADER_PAT = re.compile(re.escape(TAXON_NOTBY_HEADER) + "\n")
TAXON_LIST_DELIMITER = [", ", " > "]


async def get_taxon_preferred_establishment_means(ctx, taxon):
    """Get the preferred establishment means for the taxon."""
    try:
        establishment_means = taxon.establishment_means
        place_id = establishment_means.place.id
        if getattr(taxon, "listed_taxa", None) is None:
            taxon = await ctx.client.taxa.populate(taxon, refresh=True)
    except (AttributeError, LookupError):
        return None

    find_means = (means for means in taxon.listed_taxa if means.place.id == place_id)
    return next(find_means, establishment_means)


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
    if taxon_query.ranks and not taxon_query.terms:
        return records[0] if records else None
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
        url = obs_url_from_v1(obs_opt)
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
        url = obs_url_from_v1(obs_opt)
        if taxon and RANK_LEVELS[taxon.rank] <= RANK_LEVELS["species"]:
            link = f"[{observations_count:,}]({url}) {login}"
        else:
            link = f"[{observations_count:,} ({species_count:,})]({url}) {login}"
        return f"{link} "

    return ""


async def get_taxon(ctx: Context, taxon_id, **kwargs):
    """Get taxon by id."""
    paginator = ctx.inat_client.taxa.from_ids(taxon_id, limit=1, **kwargs)
    taxa = await paginator.async_all() if paginator else None
    return taxa[0] if taxa else None
