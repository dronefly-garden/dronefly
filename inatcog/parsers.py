"""Module to access iNaturalist API."""
import logging
from pyparsing import Word, printables, nums, Group, Suppress, OneOrMore, CaselessKeyword, oneOf

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

class BaseQueryParser():
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

        phrase_delim = '"'
        stop = oneOf(OPS + RANKS, CaselessKeyword)

        phraseword = Word(printables, excludeChars=phrase_delim)
        phrasewords = OneOrMore(phraseword)
        phrase = Group(Suppress(phrase_delim) + phrasewords + Suppress(phrase_delim))

        ranks = OneOrMore(oneOf(RANKS, CaselessKeyword))
        words = OneOrMore(Word(printables, excludeChars=phrase_delim), stopOn=stop)

        ranks_terms = Group(ranks)("ranks") + Group(OneOrMore(words | phrase, stopOn=stop))("terms")
        terms_ranks = Group(OneOrMore(words | phrase, stopOn=stop))("terms") + Group(ranks)("ranks")
        terms_unranked = Group(OneOrMore(words | phrase, stopOn=stop))("terms")
        terms = ranks_terms | terms_ranks | terms_unranked

        taxon = Group(Group(num)("taxon_id") | terms)

        within = Group(taxon + Suppress("in") + taxon) | Group(taxon)

        return within

    def parse(self, query):
        """Parse."""
        return self._grammar.parseString(query)

class TaxonQueryParser(BaseQueryParser):
    """Parser for taxon queries."""
    def __init__(self, cog):
        self.cog = cog
        self.log = cog.log
        super().__init__()
