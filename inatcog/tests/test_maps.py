"""Test maps module."""
import unittest
from unittest.mock import patch

from inatcog import maps

API_REQUESTS_PATCH = patch("inatcog.api.requests.get")


class TestMaps(unittest.TestCase):
    """Test maps module members."""

    def test_get_zoom_level(self):
        """Test get_zoom_level."""
        self.assertEqual(
            3,
            maps.get_zoom_level(
                -2.4533869111943716,
                72.54455899301723,
                -4.336453106916906,
                -33.67657572171146,
            ),
        )
        self.assertEqual(
            3,
            maps.get_zoom_level(
                58.17009894596952,
                51.98077353554603,
                36.85503840250743,
                52.26324800795092,
            ),
        )
        self.assertEqual(
            10,
            maps.get_zoom_level(
                0.04009789038412026,
                0.04546756205725333,
                0.5542028070417532,
                0.747609743195887,
            ),
        )
        self.assertEqual(10, maps.get_zoom_level(1, 2, 1, 2))
        self.assertEqual(
            10,
            maps.get_zoom_level(
                0.07292934782378639,
                0.031039528337167388,
                0.05678045092019873,
                0.00037250848038744566,
            ),
        )
        self.assertEqual(
            3,
            maps.get_zoom_level(
                -58.75873509515603,
                115.81086902171563,
                121.24429734669474,
                -75.91007582574187,
            ),
        )
        self.assertEqual(
            4,
            maps.get_zoom_level(
                26.80202232208103,
                243.17086377181113,
                36.10696497838944,
                252.41441695019603,
            ),
        )
        self.assertEqual(
            5,
            maps.get_zoom_level(
                -46.791124530136585,
                167.6235736347735,
                -41.917609381489456,
                171.4814715553075,
            ),
        )
        self.assertEqual(
            3,
            maps.get_zoom_level(
                -77.86615270189941,
                292.3406052030623,
                -60.611640913411975,
                170.43886983767152,
            ),
        )
        self.assertEqual(
            3,
            maps.get_zoom_level(
                -16.528484746813774,
                139.63242868892848,
                64.74736074451357,
                296.261251559481,
            ),
        )

    @unittest.skip("Support for coroutines needed for this test to work again.")
    def test_get_map_coords_for_taxon_ids(self):
        """Test get_map_coords_for_taxon_ids."""
        bounds_1 = {}
        bounds_2 = {
            "total_bounds": {"swlat": 58, "swlng": 51, "nelat": 36, "nelng": 52}
        }
        bounds_3 = {
            "total_bounds": {
                "swlat": -16.528484746813774,
                "swlng": 139.63242868892848,
                "nelat": 64.74736074451357,
                "nelng": -63.738748440518975,
            }
        }
        with API_REQUESTS_PATCH as mock_get:
            mock_get.return_value.json.return_value = bounds_1
            self.assertEqual(
                maps.get_map_coords_for_taxon_ids([]),
                maps.MapCoords(zoom_level=2, center_lat=0, center_lon=0),
            )

            mock_get.return_value.json.return_value = bounds_2
            self.assertEqual(
                maps.get_map_coords_for_taxon_ids([]),
                maps.MapCoords(zoom_level=3, center_lat=47.0, center_lon=51.5),
            )

            mock_get.return_value.json.return_value = bounds_3
            self.assertEqual(
                maps.get_map_coords_for_taxon_ids([]),
                maps.MapCoords(
                    zoom_level=3,
                    center_lat=24.1094379988499,
                    center_lon=217.94684012420475,
                ),
            )
