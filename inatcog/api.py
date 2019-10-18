"""Module to access iNaturalist API."""
import requests

API_BASE_URL = "https://api.inaturalist.org"
WWW_BASE_URL = "https://www.inaturalist.org"


def get_taxa(*args, **kwargs):
    """Query API for taxa matching parameters."""

    # Select endpoint based on call signature:
    # - /v1/taxa is needed for id# lookup (i.e. no kwargs["q"])
    endpoint = "/v1/taxa/autocomplete" if "q" in kwargs else "/v1/taxa"
    id_arg = f"/{args[0]}" if args else ""

    results = requests.get(
        f"{API_BASE_URL}{endpoint}{id_arg}",
        headers={"Accept": "application/json"},
        params=kwargs,
    ).json()

    return results


def get_observations(*args, **kwargs):
    """Query API for observations matching parameters."""

    # Select endpoint based on call signature:
    endpoint = "/v1/observations"
    id_arg = f"/{args[0]}" if args else ""

    results = requests.get(
        f"{API_BASE_URL}{endpoint}{id_arg}",
        headers={"Accept": "application/json"},
        params=kwargs,
    ).json()

    return results


def get_observation_bounds(taxon_ids):
    """Get the bounds for the specified observations."""
    kwargs = {
        "return_bounds": "true",
        "verifiable": "true",
        "taxon_id": ",".join(map(str, taxon_ids)),
        "per_page": 0,
    }

    result = get_observations(**kwargs)
    if "total_bounds" in result:
        return result["total_bounds"]

    return None
