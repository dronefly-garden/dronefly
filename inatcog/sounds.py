"""Module to handle sounds."""
from typing import NamedTuple


class Sound(NamedTuple):
    """An iNat sound."""

    url: str
    attribution: str
