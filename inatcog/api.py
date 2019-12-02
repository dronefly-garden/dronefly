"""Module to access iNaturalist API."""
from typing import Union
import json
import requests
from .common import LOG

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


def get_users(query: Union[int, str]):
    """Get the users for the specified login, user_id, or query."""
    if isinstance(query, int) or query.isnumeric():
        request = f"/v1/users/{query}"
    else:
        request = f"/v1/users/autocomplete?q={query}"

    try:
        results = requests.get(
            f"{API_BASE_URL}{request}", headers={"Accept": "application/json"}
        ).json()
    except json.JSONDecodeError:
        LOG.error("JSONDecodeError: %s", repr(results))
        results = None

    return results
