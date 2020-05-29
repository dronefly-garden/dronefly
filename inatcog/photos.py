"""Module to handle images."""
from typing import NamedTuple


class Photo(NamedTuple):
    """An iNat photo."""

    url: str
    attribution: str
