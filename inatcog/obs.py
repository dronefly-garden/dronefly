"""Module to work with iNat observations."""

from typing import NamedTuple


class Obs(NamedTuple):
    """A flattened representation of a single get_observations JSON result."""

    taxon: dict
    obs_id: str
    obs_on: str
    obs_by: str


def get_fields_from_results(results):
    """Map get_observations JSON results into flattened field subsets.

    Parameters
    ----------
    results: list
        The JSON results from /v1/observations.

    Returns
    -------
    list of Obs
        A list of Obs entries containing a subset of fields from the full
        JSON results.
    """

    def get_fields(record):
        return Obs(
            {},
            "",
            "",
            "",
        )

    return list(map(get_fields, results))
