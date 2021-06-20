"""Tests for UnixlikeParser."""

from ..parsers.unixlike import UnixlikeParser


# pylint: disable=missing-class-docstring disable=no-self-use disable=missing-function-docstring
class TestUnixlikeParser:
    def test_parsed_standard_order(self):
        parser = UnixlikeParser()
        parsed = parser.parse("--by benarmstrong --from nova scotia")
        assert str(parsed) == "from nova scotia by benarmstrong"

    def test_parsed_implied_of_listed_first(self):
        parser = UnixlikeParser()
        parsed = parser.parse("--by benarmstrong --of birds")
        assert str(parsed) == "birds by benarmstrong"

    # FIXME: missing tests for remaining arguments
