"""Tests for query module."""

from ..query.query import Query, TaxonQuery


# pylint: disable=missing-class-docstring disable=no-self-use disable=missing-function-docstring
class TestQuery:
    def test_query_id(self):
        query = Query(main=TaxonQuery(taxon_id=1))
        assert str(query) == "1"

    def test_query_terms(self):
        query = Query(main=TaxonQuery(terms=["song", "sparrow"]))
        assert str(query) == "song sparrow"

    def test_query_phrase(self):
        query = Query(
            main=TaxonQuery(terms=["song", "sparrow"], phrases=[["song", "sparrow"]])
        )
        assert str(query) == "song sparrow"

    def test_query_ranks(self):
        query = Query(main=TaxonQuery(terms=["song", "sparrow"], ranks=["sp", "ssp"]))
        assert str(query) == "song sparrow sp ssp"

    def test_query_code(self):
        query = Query(main=TaxonQuery(code="WTSP"))
        assert str(query) == "WTSP"

    def test_query_ancestor(self):
        query = Query(
            main=TaxonQuery(terms=["prunella"]), ancestor=TaxonQuery(terms=["animals"])
        )
        assert str(query) == "prunella in animals"
