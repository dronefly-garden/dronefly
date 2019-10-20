"""Module to work with iNat taxa."""
import re
from typing import NamedTuple
from .api import get_taxa
from .common import LOG
from .parsers import TaxonQueryParser, RANK_LEVELS

TAXON_QUERY_PARSER = TaxonQueryParser()


class Taxon(NamedTuple):
    """A taxon."""

    name: str
    taxon_id: int
    common: str or None
    term: str
    thumbnail: str or None
    rank: str
    ancestor_ids: list
    observations: int


TRINOMIAL_ABBR = {"variety": "var.", "subspecies": "ssp.", "form": "f."}


def format_taxon_names(
    taxa, with_term=False, names_format="%s", delimiter=", ", max_len=0
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

    Returns
    -------
    str
        A list of comma-delimited formatted taxon names. If 
    """

    names = [format_taxon_name(taxon, with_term=with_term) for taxon in taxa]

    def fit_names(names):
        names_fit = []
        # Account for space already used by format string (minus 2 for %s)
        available_len = max_len - (len(names_format) - 2)
        more = lambda count: "and %d more" % count
        formatted_len = lambda name: sum(
            len(item) + len(delimiter) for item in names_fit
        ) + len(name)
        overflow = lambda name: formatted_len(name) > available_len
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


def format_taxon_name(rec, with_term=False):
    """Format taxon name from matched record.

    Parameters
    ----------
    rec: Taxon
        A matched taxon record.
    with_term: bool, optional
        With non-common / non-name matching term in parentheses in place of common name.

    Returns
    -------
    str
        A name of the form "Rank Scientific name (Common name)" following the
        same basic format as iNaturalist taxon pages on the web, i.e.

        - drop the "Rank" keyword for genus level and lower
        - italicize the name (minus any rank abbreviations; see next point) for species
          level and lower
        - for trinomials (must be subspecies level & have exactly 3 names to qualify),
          insert the appropriate abbreviation, unitalicized, between the 2nd and 3rd
          name (e.g. "Anser anser domesticus" -> "*Anser anser* var. *domesticus*")
    """
    if with_term:
        common = rec.term if rec.term not in (rec.name, rec.common) else rec.common
    else:
        common = rec.common
    if RANK_LEVELS[rec.rank] > RANK_LEVELS["species"]:
        name = f"{rec.rank.capitalize()} {rec.name}"
    else:
        name = f"*{rec.name}*"
        if rec.rank in TRINOMIAL_ABBR.keys():
            tri = rec.name.split(" ")
            if len(tri) == 3:
                name = f"*{tri[0]} {tri[1]}* {TRINOMIAL_ABBR[rec.rank]} *{tri[2]}*"
    return f"{name} ({common})" if common else name


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
    photo = record.get("default_photo")
    taxon_id = record["id"] if "id" in record else record["taxon_id"]
    return Taxon(
        record["name"],
        taxon_id,
        record.get("preferred_common_name"),
        record.get("matched_term") or "Id: %s" % taxon_id,
        photo.get("square_url") if photo else None,
        record["rank"],
        record["ancestor_ids"],
        record["observations_count"],
    )


class NameMatch(NamedTuple):
    """Match for each name field in Taxon matching a pattern."""

    term: re.match or None
    name: re.match or None
    common: re.match or None


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


def score_match(query, record, all_terms, exact=None, ancestor_id=None):
    """Score a matched record. A higher score is a better match."""
    score = 0

    if query.taxon_id:
        return 1000  # An id is always the best match

    matched = match_exact(record, exact) if exact else NO_NAME_MATCH
    all_matched = match_name(record, all_terms) if query.taxon_id else NO_NAME_MATCH

    result_not_matching_filter = (
        ancestor_id and (ancestor_id not in record.ancestor_ids)
    ) or (query.ranks and (record.rank not in query.ranks))
    if result_not_matching_filter:
        # Reject; workaround to bug in /v1/taxa/autocomplete
        # - https://forum.inaturalist.org/t/v1-taxa-autocomplete/7163
        score = -1
    elif query.code and (query.code == record.term):
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


def match_taxon(query, records, ancestor_id=None):
    """Match a single taxon for the given query among records returned by API."""
    exact = []
    all_terms = re.compile(r"^%s$" % re.escape(" ".join(query.terms)), re.I)
    if query.phrases:
        for phrase in query.phrases:
            pat = re.compile(r"\b%s\b" % re.escape(" ".join(phrase)), re.I)
            exact.append(pat)
    scores = [0] * len(records)

    for num, record in enumerate(records, start=0):
        scores[num] = score_match(
            query, record, all_terms=all_terms, exact=exact, ancestor_id=ancestor_id
        )

    best_score = max(scores)
    LOG.info("Best score: %d", best_score)
    best_record = records[scores.index(best_score)]
    min_score_met = (best_score >= 0) and ((not exact) or (best_score >= 200))
    LOG.info(
        "Best match: %s%s",
        repr(best_record),
        "" if min_score_met else " (score too low)",
    )

    return best_record if min_score_met else None


def maybe_match_taxon(query, ancestor_id=None):
    """Get taxon and return a match, if any."""
    if query.taxon_id:
        records = get_taxa(query.taxon_id)["results"]
    else:
        kwargs = {}
        kwargs["q"] = " ".join(query.terms)
        if query.ranks:
            kwargs["rank"] = ",".join(query.ranks)
        if ancestor_id:
            kwargs["taxon_id"] = ancestor_id
        records = get_taxa(**kwargs)["results"]

    if not records:
        raise LookupError("Nothing found")

    taxon = match_taxon(
        query, list(map(get_taxon_fields, records)), ancestor_id=ancestor_id
    )

    if not taxon:
        raise LookupError("No exact match")

    return taxon


def maybe_match_taxon_compound(compound_query):
    """Get one or more taxon and return a match, if any.

    Currently the grammar supports only one ancestor taxon
    and one child taxon.
    """
    query_main = compound_query.main
    query_ancestor = compound_query.ancestor
    if query_ancestor:
        ancestor = maybe_match_taxon(query_ancestor)
        if ancestor:
            if query_main.ranks:
                LOG.info("query ranks = %s", ",".join(query_main.ranks))
                max_query_rank_level = max(
                    [RANK_LEVELS[rank] for rank in query_main.ranks]
                )
                LOG.info("max_query_rank_level = %3.1f", max_query_rank_level)
                ancestor_rank_level = RANK_LEVELS[ancestor.rank]
                LOG.info("ancestor_rank_level = %3.1f", ancestor_rank_level)
                if max_query_rank_level >= ancestor_rank_level:
                    raise LookupError(
                        "Child rank%s: `%s` must be below ancestor rank: `%s`"
                        % (
                            "s" if len(query_main.ranks) > 1 else "",
                            ",".join(query_main.ranks),
                            ancestor.rank,
                        )
                    )
            taxon = maybe_match_taxon(query_main, ancestor_id=ancestor.taxon_id)
    else:
        taxon = maybe_match_taxon(query_main)

    return taxon


def query_taxon(query):
    """Query for one or more taxa and return list of matching taxa."""
    compound_query = TAXON_QUERY_PARSER.parse(query)
    return maybe_match_taxon_compound(compound_query)


def query_taxa(query):
    """Query for one or more taxa and return list of matching taxa."""
    queries = list(map(TAXON_QUERY_PARSER.parse, query.split(",")))
    # De-duplicate the query via dict:
    taxa = {}
    for compound_query in queries:
        try:
            taxon = maybe_match_taxon_compound(compound_query)
            taxa[str(taxon.taxon_id)] = taxon
        except LookupError:
            pass

    result = taxa.values()
    if not result:
        raise LookupError("Nothing found")

    return result
