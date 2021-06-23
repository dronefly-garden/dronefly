"""Tests for query module."""
from datetime import datetime

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

    def test_query_user(self):
        query = Query(main=TaxonQuery(terms=["song", "sparrow"]), user="me")
        assert str(query) == "song sparrow by me"

    def test_query_place(self):
        query = Query(main=TaxonQuery(terms=["song", "sparrow"]), place="home")
        assert str(query) == "song sparrow from home"

    def test_query_controlled_term(self):
        query = Query(
            main=TaxonQuery(terms=["song", "sparrow"]), controlled_term="sex f"
        )
        assert str(query) == "song sparrow with sex f"

    def test_query_unobserved_by(self):
        query = Query(main=TaxonQuery(terms=["song", "sparrow"]), unobserved_by="me")
        assert str(query) == "song sparrow not by me"

    def test_query_id_by(self):
        query = Query(main=TaxonQuery(terms=["song", "sparrow"]), id_by="me")
        assert str(query) == "song sparrow id by me"

    def test_query_project(self):
        query = Query(
            main=TaxonQuery(terms=["song", "sparrow"]), project="inat discord server"
        )
        assert str(query) == "song sparrow in prj inat discord server"

    def test_query_per(self):
        query = Query(main=TaxonQuery(terms=["birds"]), user="me", per="species")
        assert str(query) == "birds by me per species"

    def test_query_opt(self):
        query = Query(
            main=TaxonQuery(terms=["birds"]), user="me", options=["popular", "sounds"]
        )
        assert str(query) == "birds by me opt popular sounds"

    def test_query_since(self):
        obs_d1 = datetime.now()
        query = Query(main=TaxonQuery(terms=["birds"]), user="me", obs_d1=obs_d1)
        assert str(query) == "birds by me since {}".format(obs_d1)

    def test_query_until(self):
        obs_d2 = datetime.now()
        query = Query(main=TaxonQuery(terms=["birds"]), user="me", obs_d2=obs_d2)
        assert str(query) == "birds by me until {}".format(obs_d2)

    def test_query_on(self):
        obs_on = datetime.now()
        query = Query(main=TaxonQuery(terms=["birds"]), user="me", obs_on=obs_on)
        assert str(query) == "birds by me on {}".format(obs_on)

    def test_query_added_since(self):
        added_d1 = datetime.now()
        query = Query(main=TaxonQuery(terms=["birds"]), user="me", added_d1=added_d1)
        assert str(query) == "birds by me added since {}".format(added_d1)

    def test_query_added_until(self):
        added_d2 = datetime.now()
        query = Query(main=TaxonQuery(terms=["birds"]), user="me", added_d2=added_d2)
        assert str(query) == "birds by me added until {}".format(added_d2)

    def test_query_added_on(self):
        added_on = datetime.now()
        query = Query(main=TaxonQuery(terms=["birds"]), user="me", added_on=added_on)
        assert str(query) == "birds by me added on {}".format(added_on)
