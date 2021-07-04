"""Tests for Taxon."""
# pylint: disable=missing-class-docstring, no-self-use, missing-function-docstring
# pylint: disable=redefined-outer-name

from ..models.taxon import Taxon


class TestTaxon:
    def test_taxon_is_a_taxon(self):
        taxon = Taxon(
            id=3,
            name="Birds",
            matched_term="Birds",
            rank="class",
            ancestor_ids=[48460, 1, 2, 355675, 3],
            observations_count=11645562,
            ancestor_ranks=["stateofmatter", "kingdom", "phylum", "class"],
            is_active=True,
            listed_taxa=[
                {
                    "id": 5756493,
                    "taxon_id": 3,
                    "establishment_means": "native",
                    "place": {
                        "id": 6803,
                        "name": "New Zealand",
                        "display_name": "New Zealand",
                        "admin_level": 0,
                        "ancestor_place_ids": [97393, 6803],
                    },
                    "list": {"id": 7126, "title": "New Zealand Check List"},
                },
                {
                    "id": 86811797,
                    "taxon_id": 3,
                    "establishment_means": "native",
                    "place": {
                        "id": 83350,
                        "name": "Auckland Ecological Region",
                        "display_name": "Auckland Ecological Region, NZ",
                        "admin_level": None,
                        "ancestor_place_ids": [97393, 6803, 83350],
                    },
                    "list": {
                        "id": 3848234,
                        "title": "Auckland Ecological Region Check List",
                    },
                },
                {
                    "id": 22740081,
                    "taxon_id": 3,
                    "establishment_means": "native",
                    "place": {
                        "id": 128329,
                        "name": "Auckland Isthmus",
                        "display_name": "Auckland Isthmus, NZ",
                        "admin_level": None,
                        "ancestor_place_ids": [97393, 6803, 108679, 128329],
                    },
                    "list": {"id": 1265139, "title": "Auckland Isthmus Check List"},
                },
                {
                    "id": 48895541,
                    "taxon_id": 3,
                    "establishment_means": "native",
                    "place": {
                        "id": 146883,
                        "name": "Corredor Mashpi-Cotacachi Cayapas",
                        "display_name": "Corredor Mashpi-Cotacachi Cayapas, EC",
                        "admin_level": None,
                        "ancestor_place_ids": [97389, 7512, 146883],
                    },
                    "list": {
                        "id": 2747919,
                        "title": "Corredor Mashpi-Cotacachi Cayapas Check List",
                    },
                },
            ],
            names=[
                {"is_valid": True, "name": "Aves", "position": 0, "locale": "sci"},
                {"is_valid": True, "name": "Aves", "position": 0, "locale": "es"},
                {"is_valid": True, "name": "鳥綱", "position": 1, "locale": "ja"},
                {"is_valid": True, "name": "Oiseaux", "position": 2, "locale": "fr"},
                {"is_valid": True, "name": "Birds", "position": 3, "locale": "en"},
                {"is_valid": True, "name": "Aves", "position": 4, "locale": "pt"},
                {"is_valid": True, "name": "Vögel", "position": 5, "locale": "de"},
                {"is_valid": True, "name": "Птицы", "position": 6, "locale": "ru"},
            ],
            preferred_common_name="Birds",
            thumbnail="https://inaturalist-open-data.s3.amazonaws.com/photos/222/square.jpg?1553973240",  # noqa: E501
            image="https://inaturalist-open-data.s3.amazonaws.com/photos/222/original.jpg?1553973240",  # noqa: E501
            image_attribution="(c) Kenny P., some rights reserved (CC BY-NC)",
        )

        assert isinstance(taxon, Taxon)
