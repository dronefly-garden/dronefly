"""Module to work with iNat taxa."""
import re
from typing import NamedTuple, Optional, Union
from .base_classes import (
    WWW_BASE_URL,
    RANK_LEVELS,
    EstablishmentMeans,
    EstablishmentMeansPartial,
    Taxon,
    User,
    Place,
)


TAXON_ID_LIFE = 48460
TAXON_PLACES_HEADER = "__obs# (spp#) from place:__"
TAXON_PLACES_HEADER_PAT = re.compile(re.escape(TAXON_PLACES_HEADER) + "\n")
TAXON_COUNTS_HEADER = "__obs# (spp#) by user:__"
TAXON_COUNTS_HEADER_PAT = re.compile(re.escape(TAXON_COUNTS_HEADER) + "\n")
TAXON_LIST_DELIMITER = [", ", " > "]
TAXON_PRIMARY_RANKS = ["kingdom", "phylum", "class", "order", "family"]

TRINOMIAL_ABBR = {"variety": "var.", "subspecies": "ssp.", "form": "f."}

PAT_TAXON_LINK = re.compile(
    r"\b(?P<url>https?://(www\.)?inaturalist\.(org|ca)/taxa/(?P<taxon_id>\d+))\b", re.I
)


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
        format_taxon_name(taxon, with_term=with_term, hierarchy=hierarchy)
        for taxon in taxa
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


def format_taxon_name(rec, with_term=False, hierarchy=False):
    """Format taxon name from matched record.

    Parameters
    ----------
    rec: Taxon
        A matched taxon record.
    with_term: bool, optional
        With non-common / non-name matching term in parentheses in place of common name.
    hierarchy: bool, optional
        If specified, produces a list item suitable for inclusion in the hierarchy section
        of a taxon embed. See format_taxon_names() for details.

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
    if with_term:
        common = rec.term if rec.term not in (rec.name, rec.common) else rec.common
    else:
        if hierarchy:
            common = None
        else:
            common = rec.common
    name = rec.name

    rank = rec.rank
    rank_level = RANK_LEVELS[rank]

    if rank_level <= RANK_LEVELS["genus"]:
        name = f"*{name}*"
    if rank_level > RANK_LEVELS["species"]:
        if hierarchy:
            # FIXME: List formatting concerns don't belong here. Move them up a level.
            bold = ("\n> **", "**") if rank in TAXON_PRIMARY_RANKS else ("", "")
            name = f"{bold[0]}{name}{bold[1]}"
        else:
            name = f"{rank.capitalize()} {name}"
    else:
        if rank in TRINOMIAL_ABBR.keys():
            tri = name.split(" ")
            if len(tri) == 3:
                # Note: name already italicized, so close/reopen italics around insertion.
                name = f"{tri[0]} {tri[1]}* {TRINOMIAL_ABBR[rank]} *{tri[2]}"
    full_name = f"{name} ({common})" if common else name
    if not rec.active:
        full_name += " :exclamation: Inactive Taxon"
    return full_name


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
    thumbnail = None
    photo = record.get("default_photo")
    if photo:
        thumbnail = photo.get("square_url")
        # Though default_photo only contains small versions of the image,
        # the original can be obtained for self-hosted images via this
        # transform on the thumbnail image:
        if re.search(r"https?://static\.inaturalist\.org", thumbnail):
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
        listed_taxa_iter = [
            EstablishmentMeans.from_dict(establishment_means)
            for establishment_means in listed_taxa_raw
        ]
        listed_taxa = list(listed_taxa_iter)
    else:
        listed_taxa = []
    establishment_means_raw = record.get("establishment_means")
    if establishment_means_raw:
        establishment_means = EstablishmentMeansPartial.from_dict(
            establishment_means_raw
        )
    else:
        establishment_means = None
    taxon = Taxon(
        record["name"],
        taxon_id,
        record.get("preferred_common_name"),
        record.get("matched_term") or "Id: %s" % taxon_id,
        thumbnail,
        image,
        attribution,
        record["rank"],
        record["ancestor_ids"],
        record["observations_count"],
        ancestor_ranks,
        record["is_active"],
        listed_taxa,
        establishment_means,
    )
    return taxon


class NameMatch(NamedTuple):
    """Match for each name field in Taxon matching a pattern."""

    term: Optional[re.match]
    name: Optional[re.match]
    common: Optional[re.match]


NO_NAME_MATCH = NameMatch(None, None, None)


def match_name(record, pat):
    """Match all terms specified.

    Parameters
    ----------
    record: Taxon
        A candidate taxon to match.

    pat: re.Pattern or str
        A pattern to match against each name field in the record.

    Returns
    -------
    NameMatch
        A tuple of search results for the pat for each name in the record.
    """
    return NameMatch(
        re.search(pat, record.term),
        re.search(pat, record.name),
        re.search(pat, record.common) if record.common else None,
    )


def match_exact(record, exact):
    """Match any exact phrases specified.

    Parameters
    ----------
    record: Taxon
        A candidate taxon to match.

    exact: list
        A list of exact patterns to match.

    Returns
    -------
    NameMatch
        A tuple of ORed search results for every pat for each name in
        the record, i.e. each name in the tuple is the match result from
        the first matching pattern.
    """
    matched = NO_NAME_MATCH
    try:
        for pat in exact:
            this_match = match_name(record, pat)
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


def score_match(query, record, all_terms, exact=None):
    """Score a matched record. A higher score is a better match.
    Parameters
    ----------
    query: SimpleQuery
        The query for the matched record being scored.

    record: Taxon
        A candidate taxon to match.

    all_terms: re.Pattern
        A pattern matching all terms.

    exact: list
        A list of exact patterns to match.

    Returns
    -------
    int
        score < 0 indicates the match is not a valid candidate.
        score >= 0 and score < 200 indicates a non-exact match
        score >= 200 indicates an exact match either on a phrase or the whole query
    """
    score = 0

    if query.taxon_id:
        return 1000  # An id is always the best match

    matched = match_exact(record, exact) if exact else NO_NAME_MATCH
    all_matched = match_name(record, all_terms) if query.taxon_id else NO_NAME_MATCH

    if query.code and (query.code == record.term):
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


def match_taxon(query, records):
    """Match a single taxon for the given query among records returned by API."""
    exact = []
    all_terms = re.compile(r"^%s$" % re.escape(" ".join(query.terms)), re.I)
    if query.phrases:
        for phrase in query.phrases:
            pat = re.compile(r"\b%s\b" % re.escape(" ".join(phrase)), re.I)
            exact.append(pat)
    scores = [0] * len(records)

    for num, record in enumerate(records, start=0):
        scores[num] = score_match(query, record, all_terms=all_terms, exact=exact)

    best_score = max(scores)
    best_record = records[scores.index(best_score)]
    min_score_met = (best_score >= 0) and ((not exact) or (best_score >= 200))

    return best_record if min_score_met else None


async def format_place_taxon_counts(
    cog, place: Union[Place, str], taxon: Taxon, user_id: int = None
):
    """Format user observation & species counts for taxon."""
    taxon_id = taxon.taxon_id
    if isinstance(place, str):
        place_id = place
        name = "*total*"
    else:
        place_id = place.place_id
        name = place.display_name
    obs_opt = {
        "taxon_id": taxon_id,
        "place_id": place_id,
        "per_page": 0,
        "verifiable": "true",
    }
    species_opt = {
        "taxon_id": taxon_id,
        "place_id": place_id,
        "per_page": 0,
        "verifiable": "true",
    }
    if user_id:
        obs_opt["user_id"] = user_id
        species_opt["user_id"] = user_id
    observations = await cog.api.get_observations(**obs_opt)
    species = await cog.api.get_observations("species_counts", **species_opt)
    if observations:
        observations_count = observations["total_results"]
        species_count = species["total_results"]
        url = (
            WWW_BASE_URL
            + f"/observations?taxon_id={taxon_id}&place_id={place_id}&verifiable=true"
        )
        if user_id:
            url += f"&user_id={user_id}"
        if RANK_LEVELS[taxon.rank] <= RANK_LEVELS["species"]:
            link = f"[{observations_count}]({url}) {name}"
        else:
            link = f"[{observations_count} ({species_count})]({url}) {name}"
        return f"{link} "

    return ""


async def format_user_taxon_counts(
    cog, user: Union[User, str], taxon, place_id: int = None
):
    """Format user observation & species counts for taxon."""
    taxon_id = taxon.taxon_id
    if isinstance(user, str):
        user_id = user
        login = "*total*"
    else:
        user_id = user.user_id
        login = user.login
    obs_opt = {"taxon_id": taxon_id, "user_id": user_id, "per_page": 0}
    species_opt = {"taxon_id": taxon_id, "user_id": user_id, "per_page": 0}
    if place_id:
        obs_opt["place_id"] = place_id
        species_opt["place_id"] = place_id
    observations = await cog.api.get_observations(**obs_opt)
    species = await cog.api.get_observations("species_counts", **species_opt)
    if observations:
        observations_count = observations["total_results"]
        species_count = species["total_results"]
        url = (
            WWW_BASE_URL
            + f"/observations?taxon_id={taxon_id}&user_id={user_id}&verifiable=any"
        )
        if place_id:
            url += f"&place_id={place_id}"
        if RANK_LEVELS[taxon.rank] <= RANK_LEVELS["species"]:
            link = f"[{observations_count}]({url}) {login}"
        else:
            link = f"[{observations_count} ({species_count})]({url}) {login}"
        return f"{link} "

    return ""


async def get_taxon(cog, taxon_id, **kwargs):
    """Get taxon by id."""
    taxon_record = (await cog.api.get_taxa(taxon_id, **kwargs))["results"][0]
    return get_taxon_fields(taxon_record)
