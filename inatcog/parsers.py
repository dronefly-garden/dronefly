"""Module to access iNaturalist API."""
import logging
from collections import namedtuple
from pyparsing import Word, pyparsing_unicode, nums, Group, Suppress, OneOrMore, \
     CaselessKeyword, oneOf

LOG = logging.getLogger('red.quaggagriff.inatcog')
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

OPS = (
    'in',
    'by',
    'at',
)

Query = namedtuple('Query', 'taxon_id, terms, phrases, ranks')
Queries = namedtuple('Queries', 'main, ancestor')

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
        stop = oneOf(OPS + RANKS, caseless=True, asKeyword=True)

        phraseword = Word(pyparsing_unicode.printables, excludeChars=dqt)
        phrase = Group(Suppress(dqt) + OneOrMore(phraseword) + Suppress(dqt))

        ranks = OneOrMore(oneOf(RANKS, caseless=True, asKeyword=True))
        words = OneOrMore(Word(pyparsing_unicode.printables, excludeChars=dqt), stopOn=stop)

        ranks_terms = Group(ranks)("ranks") + Group(OneOrMore(words | phrase, stopOn=stop))("terms")
        terms_ranks = Group(OneOrMore(words | phrase, stopOn=stop))("terms") + Group(ranks)("ranks")
        terms = Group(OneOrMore(words | phrase, stopOn=stop))("terms")

        taxon = Group(Group(num)("taxon_id") | ranks_terms | terms_ranks | terms)

        within = (
            Group(taxon)("main") + Suppress(CaselessKeyword('in')) + Group(taxon)("ancestor")
        ) | Group(taxon)("main")

        return within

    def get_taxon_query_args(self, parsed):
        """Return namedtuple representing query for a taxon."""
        terms = phrases = ranks = []
        taxon_id = None
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
        return Query(taxon_id=taxon_id, terms=terms, phrases=phrases, ranks=ranks)

    def parse(self, query_str):
        """Parse using taxon query grammar."""
        parsed = self._grammar.parseString(query_str)
        LOG.info(parsed.dump())
        ancestor = None
        if parsed:
            LOG.info(parsed["main"][0])
            main = self.get_taxon_query_args(parsed["main"][0])
            try:
                LOG.info(parsed["ancestor"][0])
                ancestor = self.get_taxon_query_args(parsed["ancestor"][0])
            except KeyError:
                pass
        return Queries(main=main, ancestor=ancestor)
