"""Test inatcog.api."""
import unittest
from unittest.mock import patch

from inatcog import api

API_REQUESTS_PATCH = patch("inatcog.api.requests.get")


class TestAPI(unittest.TestCase):
    @unittest.skip("Support for coroutines needed for this test to work again.")
    def test_get_taxa_by_id(self):
        """Test get_taxa by id."""
        expected_result = {"results": [{"name": "Animalia"}]}

        with API_REQUESTS_PATCH as mock_get:
            mock_get.return_value.json.return_value = expected_result
            self.assertEqual(api.get_taxa(1)["results"][0]["name"], "Animalia")

    @unittest.skip("Support for coroutines needed for this test to work again.")
    def test_get_taxa_by_query(self):
        """Test get_taxa with query terms."""
        expected_result = {"results": [{"name": "Animalia"}]}

        with API_REQUESTS_PATCH as mock_get:
            mock_get.return_value.json.return_value = expected_result
            self.assertEqual(
                api.get_taxa(q="animals")["results"][0]["name"], "Animalia"
            )

    @unittest.skip("Support for coroutines needed for this test to work again.")
    def test_get_observation_bounds(self):
        """Test get_observation_bounds."""
        expected_result_1 = {}
        expected_result_2 = {
            "total_bounds": {"swlat": 1, "swlng": 2, "nelat": 3, "nelng": 4}
        }

        with API_REQUESTS_PATCH as mock_get:
            mock_get.return_value.json.return_value = expected_result_1
            self.assertIsNone(api.get_observation_bounds([]))
            self.assertIsNone(api.get_observation_bounds(["1"]))

            mock_get.return_value.json.return_value = expected_result_2
            self.assertDictEqual(
                api.get_observation_bounds(["1"]), expected_result_2["total_bounds"]
            )

    @unittest.skip("Support for coroutines needed for this test to work again.")
    def test_get_users_by_id(self):
        """Test get_users by id."""
        expected_result = {"results": [{"login": "benarmstrong"}]}

        with API_REQUESTS_PATCH as mock_get:
            mock_get.return_value.json.return_value = expected_result
            self.assertEqual(
                api.get_users(545640)["results"][0]["login"], "benarmstrong"
            )

    @unittest.skip("Support for coroutines needed for this test to work again.")
    def test_get_users_by_login(self):
        """Test get_users by login."""
        expected_result = {"results": [{"login": "benarmstrong"}]}

        with API_REQUESTS_PATCH as mock_get:
            mock_get.return_value.json.return_value = expected_result
            self.assertEqual(
                api.get_users("benarmstrong")["results"][0]["login"], "benarmstrong"
            )

    @unittest.skip("Support for coroutines needed for this test to work again.")
    def test_get_users_by_name(self):
        """Test get_users by name."""
        expected_result = {
            "results": [{"login": "benarmstrong"}, {"login": "bensomebodyelse"}]
        }

        with API_REQUESTS_PATCH as mock_get:
            mock_get.return_value.json.return_value = expected_result
            self.assertEqual(
                api.get_users("Ben Armstrong")["results"][1]["login"], "bensomebodyelse"
            )
