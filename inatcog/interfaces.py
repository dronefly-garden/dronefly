"""Module for abc interfaces."""

from abc import ABC
from asyncio import Event
from inflect import engine
from redbot.core import Config
from redbot.core.bot import Red
from .api import INatAPI
from .places import INatPlaceTable
from .users import INatUserTable


class MixinMeta(ABC):
    """
    Metaclass for well behaved type hint detection with composite class.
    """

    # https://github.com/python/mypy/issues/1996

    def __init__(self, *_args):
        self.config: Config
        self.api: INatAPI
        self.bot: Red
        self.p: engine  # pylint: disable=invalid-name
        self.user_table: INatUserTable
        self.reaction_locks: dict
        self.predicate_locks: dict
        self.place_table: INatPlaceTable
        self._ready_event: Event
