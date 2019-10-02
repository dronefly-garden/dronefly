"""Module to access iNaturalist API."""
import logging
from abc import ABC, abstractmethod
from pyparsing import Word, alphanums, Group, Forward, Suppress

LOG = logging.getLogger('red.quaggagriff.inatcog')

class BaseTaxonQueryParser(ABC):
    # pylint: disable=no-self-use
    """
    Abstract base parser for taxon queries.

    Based on https://raw.githubusercontent.com/pyparsing/pyparsing/master/examples/searchparser.py
    but with simplified grammar.
    """
    def __init__(self):
        self._methods = {
            # TODO: 'in': self.evaluate_in,
            'and': self.evaluate_and,
            'quotes': self.evaluate_quotes,
            'word': self.evaluate_word,
            # TODO: 'id': self.evaluate_id,
        }
        self._parser = self.parser()

    def parser(self):
        # pylint: disable=pointless-statement
        # pylint: disable=expression-not-assigned
        """Return a parser."""
        op_word = Group(Word(alphanums)).setResultsName('word')

        op_quotes_content = Forward()
        op_quotes_content << ((op_word + op_quotes_content) | op_word)

        op_quotes = Group(
            Suppress('"') + op_quotes_content + Suppress('"')
        ).setResultsName("quotes") | op_word

        op_and = Forward()
        op_and << (Group(op_quotes + op_and).setResultsName("and") | op_quotes)

        return op_and.parseString

    def evaluate_and(self, argument):
        """Evaluate intersection of arguments."""
        return self.evaluate(argument[0]).intersection(self.evaluate(argument[1]))

    def evaluate_quotes(self, argument):
        """Evaluate quoted strings

        First it does an 'and' on the individual search terms, then it asks the
        function get_quoted to only return the subset of ID's that contain the
        literal string.
        """
        result = set()
        search_terms = []
        for item in argument:
            search_terms.append(item[0])
            if result:
                result = result.intersection(self.evaluate(item))
            else:
                result = self.evaluate(item)
        return self.get_quotes(' '.join(search_terms), result)

    def evaluate_word(self, argument):
        """Evaluate word."""
        return self.get_word(argument[0])

    def evaluate(self, argument):
        """Evaluate."""
        return self._methods[argument.getName()](argument)

    def parse(self, query):
        """Parse."""
        return self.evaluate(self._parser(query)[0])

    @abstractmethod
    def get_word(self, word):
        """Abstract get word. Returns a set matching the word (empty if unmatched)."""
        return set()

    @abstractmethod
    def get_quotes(self, search_string, tmp_result):
        """Abstract get quoted phrase. Returns a set matching the phrase (empty if unmatched)."""
        return set()

class TaxonQueryParser(BaseTaxonQueryParser):
    """Parser for taxon queries."""
    def __init__(self, cog):
        self.cog = cog
        self.log = cog.log
        super().__init__()

    def parse(self, query):
        return self.evaluate(self._parser(query)[0])

    def get_word(self, word):
        """Returns a set matching the word (empty if unmatched)."""
        # FIXME: Always matches fictitous record 1; match actual records
        return set({1})

    def get_quotes(self, search_string, tmp_result):
        """Returns a set matching the phrase (empty if unmatched)."""
        # FIXME: Always matches fictitious record 1; match actual records
        return set({1})
