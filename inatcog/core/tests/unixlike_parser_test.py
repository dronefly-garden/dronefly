"""Tests for UnixlikeParser."""
# pylint: disable=missing-class-docstring, no-self-use, missing-function-docstring
# pylint: disable=redefined-outer-name
import re

import pytest

from ..parsers.unixlike import UnixlikeParser


@pytest.fixture
def parser():
    return UnixlikeParser()


class TestUnixlikeParser:
    def test_standard_order(self, parser):
        parsed = parser.parse("--by benarmstrong --from nova scotia")
        assert str(parsed) == "from nova scotia by benarmstrong"

    def test_implied_taxon_listed_first(self, parser):
        parsed = parser.parse("--by benarmstrong --of birds")
        assert str(parsed) == "birds by benarmstrong"

    def test_ancestor_without_main(self, parser):
        with pytest.raises(ValueError) as err:
            parser.parse("--in animals")
            assert re.match(r"Missing.*taxon", str(err), re.I)

    def test_ancestor_with_main(self, parser):
        parsed = parser.parse("--of prunella --in animals")
        assert str(parsed) == "prunella in animals"
