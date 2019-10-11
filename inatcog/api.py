"""Module to access iNaturalist API."""
import requests

BASE_URL = "https://api.inaturalist.org"

def get_taxa(*args, **kwargs):
    """Query API for taxa matching parameters."""

    # Select endpoint based on call signature:
    # - /v1/taxa is needed for id# lookup (i.e. no kwargs["q"])
    endpoint = "/v1/taxa/autocomplete" if "q" in kwargs else "/v1/taxa"
    id_arg = f"/{args[0]}" if args else ""

    results = requests.get(
        f"{BASE_URL}{endpoint}{id_arg}",
        headers={"Accept": "application/json"},
        params=kwargs,
    ).json()["results"]

    return results

def get_observations(*args, **kwargs):
    """Query API for observations matching parameters."""

    # Select endpoint based on call signature:
    endpoint = "/v1/observations"
    id_arg = f"/{args[0]}" if args else ""

    results = requests.get(
        f"{BASE_URL}{endpoint}{id_arg}",
        headers={"Accept": "application/json"},
        params=kwargs,
    ).json()["results"]

    return results
