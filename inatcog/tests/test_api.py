"""Test inatcog.api."""
import unittest
from unittest.mock import patch

from inatcog import api


class TestAPI(unittest.TestCase):
    def test_get_taxa_by_id(self):
        """Test get_taxa by id."""
        expected_result = {"results": [{"name": "Animalia"}]}

        with patch("inatcog.api.requests.get") as mock_get:
            mock_get.return_value.json.return_value = expected_result
            self.assertEqual(api.get_taxa(1)["results"][0]["name"], "Animalia")

    def test_get_taxa_by_query(self):
        """Test get_taxa with query terms."""
        expected_result = {"results": [{"name": "Animalia"}]}

        with patch("inatcog.api.requests.get") as mock_get:
            mock_get.return_value.json.return_value = expected_result
            self.assertEqual(
                api.get_taxa(q="animals")["results"][0]["name"], "Animalia"
            )

    def test_get_observation_bounds(self):
        expected_result_1 = {}
        expected_result_2 = {
            "total_bounds": {"swlat": 1, "swlng": 2, "nelat": 3, "nelng": 4}
        }

        with patch("inatcog.api.requests.get") as mock_get:
            mock_get.return_value.json.return_value = expected_result_1
            self.assertIsNone(api.get_observation_bounds([]))
            self.assertIsNone(api.get_observation_bounds(["1"]))

            mock_get.return_value.json.return_value = expected_result_2
            self.assertDictEqual(
                api.get_observation_bounds(["1"]), expected_result_2["total_bounds"]
            )
