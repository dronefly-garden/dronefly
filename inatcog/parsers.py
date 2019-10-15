"""Module providing parsers for natural language query DSLs."""
from collections import namedtuple
from pyparsing import (
    Word,
    pyparsing_unicode,
    nums,
    Group,
    Suppress,
    OneOrMore,
    CaselessKeyword,
    oneOf,
)

# RANK_LEVELS and RANK_EQUIVALENTS are from:
# - https://github.com/inaturalist/inaturalist/blob/master/app/models/taxon.rb
RANK_LEVELS = {
    # "stateofmatter": 100,
    "kingdom": 70,
    "phylum": 60,
    "subphylum": 57,
    "superclass": 53,
    "class": 50,
    "subclass": 47,
    "infraclass": 45,
    "subterclass": 44,
    "superorder": 43,
    "order": 40,
    "suborder": 37,
    "infraorder": 35,
    "parvorder": 34.5,
    "zoosection": 34,
    "zoosubsection": 33.5,
    "superfamily": 33,
    "epifamily": 32,
    "family": 30,
    "subfamily": 27,
    "supertribe": 26,
    "tribe": 25,
    "subtribe": 24,
    "genus": 20,
    "genushybrid": 20,
    "subgenus": 15,
    "section": 13,
    "subsection": 12,
    "complex": 11,
    "species": 10,
    "hybrid": 10,
    "subspecies": 5,
    "variety": 5,
    "form": 5,
    "infrahybrid": 5,
}

RANK_EQUIVALENTS = {
    "division": "phylum",
    "sub-class": "subclass",
    "super-order": "superorder",
    "sub-order": "suborder",
    "super-family": "superfamily",
    "sub-family": "subfamily",
    "gen": "genus",
    "sp": "species",
    "spp": "species",
    "infraspecies": "subspecies",
    "ssp": "subspecies",
    "sub-species": "subspecies",
    "subsp": "subspecies",
    "trinomial": "subspecies",
    "var": "variety",
    # 'unranked': None,
}

OPS = ("in", "by", "at")

SimpleQuery = namedtuple("SimpleQuery", "taxon_id, terms, phrases, ranks, code")
CompoundQuery = namedtuple("CompoundQuery", "main, ancestor")


class TaxonQueryParser:
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
        stop = oneOf(
            OPS + tuple(RANK_LEVELS.keys()) + tuple(RANK_EQUIVALENTS.keys()),
            caseless=True,
            asKeyword=True,
        )

        phraseword = Word(pyparsing_unicode.printables, excludeChars=dqt)
        phrase = Group(Suppress(dqt) + OneOrMore(phraseword) + Suppress(dqt))

        def get_abbr(_s, _l, term):
            return RANK_EQUIVALENTS[term[0]]

        ranks = OneOrMore(
            oneOf(RANK_LEVELS.keys(), caseless=True, asKeyword=True)
            | oneOf(
                RANK_EQUIVALENTS.keys(), caseless=True, asKeyword=True
            ).setParseAction(get_abbr)
        )

        words = OneOrMore(
            Word(pyparsing_unicode.printables, excludeChars=dqt), stopOn=stop
        )

        ranks_terms = Group(ranks)("ranks") + Group(
            OneOrMore(words | phrase, stopOn=stop)
        )("terms")
        terms_ranks = Group(OneOrMore(words | phrase, stopOn=stop))("terms") + Group(
            ranks
        )("ranks")
        terms = Group(OneOrMore(words | phrase, stopOn=stop))("terms")

        taxon = Group(Group(num)("taxon_id") | ranks_terms | terms_ranks | terms)

        within = (
            Group(taxon)("main")
            + Suppress(CaselessKeyword("in"))
            + Group(taxon)("ancestor")
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
                taxon_id=taxon_id, terms=terms, phrases=phrases, ranks=ranks, code=code
            )

        parsed = self._grammar.parseString(query_str)
        ancestor = None
        if parsed:
            main = get_simple_query(parsed["main"][0])
            try:
                ancestor = get_simple_query(parsed["ancestor"][0])
            except KeyError:
                pass
        return CompoundQuery(main=main, ancestor=ancestor)