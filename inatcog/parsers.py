"""Module providing parsers for natural language query DSLs."""
from collections import namedtuple
from pyparsing import (
    Word,
    pyparsing_unicode,
    nums,
    Group,
    Suppress,
    OneOrMore,
    Optional,
    CaselessKeyword,
    oneOf,
)
from .common import LOG

# RANK_LEVELS and RANK_EQUIVALENTS are from:
# - https://github.com/inaturalist/inaturalist/blob/master/app/models/taxon.rb
RANK_LEVELS = {
    "stateofmatter": 100,
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

RANK_KEYWORDS = tuple(RANK_LEVELS.keys()) + tuple(RANK_EQUIVALENTS.keys())
# These are Unicode characters that are either symbols, or else are letters
# & diacritics from foreign names that may be known to English speakers
# (e.g. Hawaiian common names).
# - See: https://github.com/synrg/dronefly/issues/57
# - Hybrids:
#   - Anas × Mareca (from Latin1.printables)
# - Hawaiian common names:
#   - ʻAlae ʻula
#   - Note: Hawaiian ʻokina is not the same as curly apostrophe even though similar!
#   - Hawaiian has some characters in LatinA
TAXON_NAME_CHARS = (
    "ʻ" + pyparsing_unicode.Latin1.printables + pyparsing_unicode.LatinA.printables
)

OPS = ("in", "by", "at", "from")

SimpleQuery = namedtuple("SimpleQuery", "taxon_id, terms, phrases, ranks, code")
CompoundQuery = namedtuple("CompoundQuery", "main, ancestor, user, place, group_by")


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
        stop = oneOf(OPS + RANK_KEYWORDS, caseless=True, asKeyword=True)

        phraseword = Word(TAXON_NAME_CHARS, excludeChars=dqt)
        phrase = Group(Suppress(dqt) + OneOrMore(phraseword) + Suppress(dqt))

        def get_abbr(_s, _l, term):
            return RANK_EQUIVALENTS[term[0]]

        ranks = OneOrMore(
            oneOf(RANK_LEVELS.keys(), caseless=True, asKeyword=True)
            | oneOf(
                RANK_EQUIVALENTS.keys(), caseless=True, asKeyword=True
            ).setParseAction(get_abbr)
        )

        words = OneOrMore(Word(TAXON_NAME_CHARS, excludeChars=dqt), stopOn=stop)

        ranks_terms = Group(ranks)("ranks") + Group(
            OneOrMore(words | phrase, stopOn=stop)
        )("terms")
        terms_ranks = Group(OneOrMore(words | phrase, stopOn=stop))("terms") + Group(
            ranks
        )("ranks")
        terms = Group(OneOrMore(words | phrase, stopOn=stop))("terms")

        taxon = Group(Group(num)("taxon_id") | ranks_terms | terms_ranks | terms)
        compound_taxon = (
            Group(taxon)("main")
            + Suppress(CaselessKeyword("in"))
            + Group(taxon)("ancestor")
        ) | Group(taxon)("main")

        from_place = Suppress(CaselessKeyword("from")) + Group(words)("place")
        by_user = Suppress(CaselessKeyword("by")) + Group(words)("user")
        qualified_taxon = compound_taxon + Optional(
            from_place + by_user | by_user + from_place | from_place | by_user
        )

        return qualified_taxon

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
            if "user" in parsed:
                user = " ".join(parsed["user"].asList())
            else:
                user = None
            if "place" in parsed:
                place = " ".join(parsed["place"].asList())
            else:
                place = None
            option_keys = [key for key in parsed.asDict() if key in ["user", "place"]]
            LOG.info(repr(parsed))
            LOG.info(repr(option_keys))
            if len(option_keys) > 1:
                group_by = option_keys[0]
            else:
                group_by = None
        return CompoundQuery(
            main=main, ancestor=ancestor, user=user, place=place, group_by=group_by
        )
