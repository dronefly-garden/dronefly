"""Module to access iNaturalist API."""
from collections import namedtuple
from pyparsing import Word, pyparsing_unicode, nums, Group, Suppress, OneOrMore, \
     CaselessKeyword, oneOf
from .common import LOG

RANKS = (
    'kingdom',
    'phylum',
    'subphylum',
    'superclass',
    'class',
    'subclass',
    'superorder',
    'order',
    'suborder',
    'infraorder',
    'superfamily',
    'epifamily',
    'family',
    'subfamily',
    'supertribe',
    'tribe',
    'subtribe',
    'genus',
    'genushybrid',
    'species',
    'hybrid',
    'subspecies',
    'variety',
    'form',
)

ABBR = {
    'sp': 'species',
    'ssp': 'subspecies',
    'var': 'variety',
}

OPS = (
    'in',
    'by',
    'at',
)

SimpleQuery = namedtuple('SimpleQuery', 'taxon_id, terms, phrases, ranks, code')
CompoundQuery = namedtuple('CompoundQuery', 'main, ancestor')

class TaxonQueryParser():
    # pylint: disable=no-self-use
    """
    Base parser for all query grammars.
    """
    def __init__(self):
        self._grammar = self.grammar()

    def grammar(self):
        # pylint: disable=pointless-statement
        # pylint: disable=expression-not-assigned
        """Return a grammar."""
        num = Word(nums)

        dqt = '"'
        stop = oneOf(OPS + RANKS + tuple(ABBR.keys()), caseless=True, asKeyword=True)

        phraseword = Word(pyparsing_unicode.printables, excludeChars=dqt)
        phrase = Group(Suppress(dqt) + OneOrMore(phraseword) + Suppress(dqt))

        def get_abbr(_s, _l, term):
            return ABBR[term[0]]

        ranks = OneOrMore(
            oneOf(RANKS, caseless=True, asKeyword=True) | \
            oneOf(ABBR.keys(), caseless=True, asKeyword=True).setParseAction(get_abbr)
        )

        words = OneOrMore(Word(pyparsing_unicode.printables, excludeChars=dqt), stopOn=stop)

        ranks_terms = Group(ranks)("ranks") + Group(OneOrMore(words | phrase, stopOn=stop))("terms")
        terms_ranks = Group(OneOrMore(words | phrase, stopOn=stop))("terms") + Group(ranks)("ranks")
        terms = Group(OneOrMore(words | phrase, stopOn=stop))("terms")

        taxon = Group(Group(num)("taxon_id") | ranks_terms | terms_ranks | terms)

        within = (
            Group(taxon)("main") + Suppress(CaselessKeyword('in')) + Group(taxon)("ancestor")
        ) | Group(taxon)("main")

        return within

    def parse(self, query_str):
        """Parse using taxon query grammar."""
        def get_simple_query(parsed):
            """Return namedtuple representing query for a taxon."""
            terms = phrases = ranks = []
            taxon_id = code = None
            if "taxon_id" in parsed:
                taxon_id = int(parsed["taxon_id"][0])
            else:
                terms = []
                phrases = []
                for term in parsed["terms"].asList():
                    if isinstance(term, list):
                        terms += term
                        phrases.append(term)
                    else:
                        terms.append(term)
                if "ranks" in parsed:
                    ranks = parsed["ranks"].asList()
                if not phrases and (len(terms) == 1) and (len(terms[0]) == 4):
                    code = terms[0].upper()
                else:
                    code = None
            return SimpleQuery(
                taxon_id=taxon_id,
                terms=terms,
                phrases=phrases,
                ranks=ranks,
                code=code,
            )

        parsed = self._grammar.parseString(query_str)
        LOG.info(parsed.dump())
        ancestor = None
        if parsed:
            LOG.info(parsed["main"][0])
            main = get_simple_query(parsed["main"][0])
            try:
                LOG.info(parsed["ancestor"][0])
                ancestor = get_simple_query(parsed["ancestor"][0])
            except KeyError:
                pass
        return CompoundQuery(main=main, ancestor=ancestor)
