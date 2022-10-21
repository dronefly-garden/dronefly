"""Module to make maps for iNat."""
from collections import namedtuple
import math
from .base_classes import WWW_BASE_URL

MapCoords = namedtuple("MapCoords", "zoom_level, center_lat, center_lon")
MapLink = namedtuple("MapLink", "title, url")


def normalize_longitude(deg):
    """Account for wrap around the globe."""
    while deg < 0:
        deg += 360
    while deg > 360:
        deg -= 360
    return deg


def get_zoom_level(swlat, swlng, nelat, nelng):
    """Get zoom level from coordinate pairs."""
    west = min(swlng, nelng)
    east = max(swlng, nelng)
    angle = east - west

    north = max(swlat, nelat)
    south = min(swlat, nelat)
    angle2 = north - south
    delta = 0

    if angle2 > angle:
        angle = angle2
        delta = 3

    if angle < 0:
        angle += 360

    if angle == 0:
        return 10

    result = int(math.log2(394 / angle)) + 2 - delta
    if result > 10:
        result = 10
    if result < 2:
        result = 2
    return result


class INatMapURL:
    """Make URL for iNat range map via /taxa/map interface on website."""

    def __init__(self, api):
        self.api = api

    async def get_map_coords_for_taxon_ids(self, taxon_ids):
        """Get map coordinates encompassing taxa ranges/observations."""
        bounds = await self.api.get_observation_bounds(taxon_ids)
        if not bounds:
            center_lat = 0
            center_lon = 0
            zoom_level = 2
        else:
            swlat = bounds["swlat"]
            swlng = normalize_longitude(bounds["swlng"])
            nelat = bounds["nelat"]
            nelng = normalize_longitude(bounds["nelng"])
            center_lat = (swlat + nelat) / 2
            center_lon = (swlng + nelng) / 2

            zoom_level = get_zoom_level(swlat, swlng, nelat, nelng)

        return MapCoords(zoom_level, center_lat, center_lon)

    async def get_map_url_for_taxa(self, taxa):
        """Get a map url for taxa from the provided coords."""

        taxon_ids = [taxon.id for taxon in taxa]
        map_coords = await self.get_map_coords_for_taxon_ids(taxon_ids)
        zoom_lat_lon = "/".join(map(str, map_coords))
        taxon_ids_str = ",".join(map(str, taxon_ids))
        url = f"{WWW_BASE_URL}/taxa/map?taxa={taxon_ids_str}#{zoom_lat_lon}"

        return url
