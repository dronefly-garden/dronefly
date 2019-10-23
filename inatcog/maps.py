"""Module to make maps for iNat."""
from collections import namedtuple
import math
from .api import get_observation_bounds, WWW_BASE_URL

MapCoords = namedtuple("MapCoords", "zoom_level, center_lat, center_lon")
MapLink = namedtuple("MapLink", "title, url")


def normalize_longitude(d):
    while d < 0:
        d += 360
    while d > 360:
        d -= 360
    return d


def calc_distance(lat1, lon1, lat2, lon2):
    """Calculate distance from coordinate pairs."""
    # pylint: disable=invalid-name
    r = 6371
    p1 = lat1 * math.pi / 180
    p2 = lat2 * math.pi / 180
    d1 = (lat2 - lat1) * math.pi / 180
    d2 = (lon2 - lon1) * math.pi / 180
    a = math.sin(d1 / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d2 / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return r * c


def get_zoom_level(swlat, swlng, nelat, nelng):
    """Get zoom level from coordinate pairs."""
    # pylint: disable=invalid-name
    d1 = calc_distance(swlat, swlng, nelat, swlng)
    d2 = calc_distance(swlat, nelng, nelat, nelng)

    arc_size = max(d1, d2)

    if arc_size == 0:
        return 10

    result = int(math.log2(20000 / arc_size) + 2)
    if result > 10:
        result = 10
    if result < 2:
        result = 2
    return result


def get_map_coords_for_taxon_ids(taxon_ids):
    """Get map coordinates encompassing taxa ranges/observations."""
    bounds = get_observation_bounds(taxon_ids)
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


def get_map_url_for_taxa(taxa):
    """Get a map url for taxa from the provided coords."""

    taxon_ids = [taxon.taxon_id for taxon in taxa]
    map_coords = get_map_coords_for_taxon_ids(taxon_ids)
    zoom_lat_lon = "/".join(map(str, map_coords))
    taxon_ids_str = ",".join(map(str, taxon_ids))
    url = f"{WWW_BASE_URL}/taxa/map?taxa={taxon_ids_str}#{zoom_lat_lon}"

    return url
