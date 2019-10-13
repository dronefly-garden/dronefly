"""Module to work with iNat taxa."""
import re
from typing import NamedTuple
from .api import get_taxa, WWW_BASE_URL
from .common import LOG
from .embeds import make_embed
from .parsers import TaxonQueryParser, RANKS

TAXON_QUERY_PARSER = TaxonQueryParser()
class Taxon(NamedTuple):
    """A flattened representation of a single get_taxa JSON result."""
    name: str
    taxon_id: int
    common: str
    term: str
    thumbnail: dict
    rank: str
    ancestor_ids: list
    observations: int

def get_fields_from_results(results):
    """Map get_taxa results into namedtuples of selected fields.

    Args:
        results (list): The JSON results from /v1/taxa or /v1/taxa/autocomplete.

    Returns:
        namedtuple: A flattened representation of the JSON result as a namedtuple.
    """
    def get_fields(record):
        photo = record.get('default_photo')
        return Taxon(
            record['name'],
            record['id'] if 'id' in record else record['taxon_id'],
            record.get('preferred_common_name'),
            record.get('matched_term'),
            photo.get('square_url') if photo else None,
            record['rank'],
            record['ancestor_ids'],
            record['observations_count'],
        )

    return list(map(get_fields, results))

class NameMatch(NamedTuple):
    """Match for each name field in Taxon matching a pattern."""
    term: re.Match
    name: re.Match
    common: re.Match

NO_NAME_MATCH = NameMatch(None, None, None)
def match_name(record, pat):
    """Match all terms specified."""
    return NameMatch(
        re.search(pat, record.term),
        re.search(pat, record.name),
        re.search(pat, record.common) if record.common else None,
    )

def match_exact(record, exact):
    """Match any exact phrases specified."""
    matched = NO_NAME_MATCH
    try:
        for pat in exact:
            this_match = match_name(pat, record)
            if this_match == NO_NAME_MATCH:
                matched = this_match
                raise ValueError('At least one field must match.')
            matched = (
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
        return 1000 # An id is always the best match

    matched = match_exact(record, exact) if exact else NO_NAME_MATCH
    all_matched = match_name(record, all_terms) if query.taxon_id else NO_NAME_MATCH

    if ancestor_id and (ancestor_id not in record.ancestor_ids):
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
    all_terms = re.compile(r'^%s$' % re.escape(' '.join(query.terms)), re.I)
    if query.phrases:
        for phrase in query.phrases:
            pat = re.compile(r'\b%s\b' % re.escape(' '.join(phrase)), re.I)
            exact.append(pat)
    scores = [0] * len(records)

    for num, record in enumerate(records, start=0):
        scores[num] = score_match(
            query,
            record,
            all_terms=all_terms,
            exact=exact,
            ancestor_id=ancestor_id
        )

    best_score = max(scores)
    LOG.info('Best score: %d', best_score)
    best_record = records[scores.index(best_score)]
    min_score_met = (best_score >= 0) and ((not exact) or (best_score >= 200))
    LOG.info('Best match: %s%s', repr(best_record), '' if min_score_met else ' (score too low)')

    return best_record if min_score_met else None

def maybe_match_taxon(query, ancestor_id=None):
    """Get taxon and return a match, if any."""
    if query.taxon_id:
        records = get_taxa(query.taxon_id)["results"]
    else:
        kwargs = {}
        # Initial space (+) stabilises order of results when upper/lowercase differs
        kwargs["q"] = '+' + ' '.join(query.terms)
        if query.ranks:
            kwargs["rank"] = ','.join(query.ranks)
        if ancestor_id:
            kwargs["taxon_id"] = ancestor_id
        records = get_taxa(**kwargs)["results"]

    if not records:
        raise LookupError('Nothing found')

    rec = match_taxon(query, get_fields_from_results(records), ancestor_id=ancestor_id)
    if not rec:
        raise LookupError('No exact match')

    return rec

def maybe_match_taxon_compound(compound_query):
    """Get one or more taxon and return a match, if any.

    Currently the grammar supports only one ancestor taxon
    and one child taxon.
    """
    query_main = compound_query.main
    query_ancestor = compound_query.ancestor
    if query_ancestor:
        rec = maybe_match_taxon(query_ancestor)
        if rec:
            index = RANKS.index(rec.rank)
            ancestor_ranks = set(RANKS[index:len(RANKS)])
            child_ranks = set(query_main.ranks)
            if child_ranks != set() and ancestor_ranks.intersection(child_ranks) == set():
                raise LookupError('Child ranks must be below ancestor rank: %s' % rec.rank)
            rec = maybe_match_taxon(query_main, ancestor_id=rec.taxon_id)
    else:
        rec = maybe_match_taxon(query_main)

    return rec

def query_taxon(query):
    """Query for one or more taxa and return list of matching taxa."""
    compound_query = TAXON_QUERY_PARSER.parse(query)
    return maybe_match_taxon_compound(compound_query)

def query_taxa(query):
    """Query for one or more taxa and return list of matching taxa."""
    queries = list(map(TAXON_QUERY_PARSER.parse, query.split(',')))
    taxa = {}
    for compound_query in queries:
        rec = maybe_match_taxon_compound(compound_query)
        taxa[str(rec.taxon_id)] = rec
    return taxa

def make_taxa_embed(rec):
    """Make embed describing taxa record."""
    embed = make_embed(
        title='{name} ({common})'.format_map(rec._asdict()) if rec.common else rec.name,
        url=f'{WWW_BASE_URL}/taxa/{rec.taxon_id}',
    )

    if rec.thumbnail:
        embed.set_thumbnail(url=rec.thumbnail)

    matched = rec.term or f'Id: {rec.taxon_id}'
    if matched not in (rec.name, rec.common):
        embed.description = matched

    observations = rec.observations
    embed.add_field(name='Observations:', value=observations, inline=True)

    return embed
