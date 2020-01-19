"""Module for abc interfaces."""

from abc import ABC
from inflect import engine
from redbot.core import Config
from redbot.core.bot import Red
from .api import INatAPI
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
