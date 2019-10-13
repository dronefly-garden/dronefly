"""Module to work with iNat taxa."""
import logging
import re
from collections import namedtuple

LOG = logging.getLogger('red.quaggagriff.inatcog')

Taxon = namedtuple(
    'Taxon',
    'name, taxon_id, common, term, thumbnail, rank, ancestor_ids, observations',
)
def get_fields_from_results(results):
    """Map get_taxa results into namedtuples of selected fields."""
    def get_fields(record):
        photo = record.get('default_photo')
        rec = Taxon(
            record['name'],
            record['id'] if 'id' in record else record['taxon_id'],
            record.get('preferred_common_name'),
            record.get('matched_term'),
            photo.get('square_url') if photo else None,
            record['rank'],
            record['ancestor_ids'],
            record['observations_count'],
        )
        return rec
    return list(map(get_fields, results))

NameMatch = namedtuple('NameMatch', 'term, name, common')
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
