"""Module for abc interfaces."""

from abc import ABC
from asyncio import Event
from inflect import engine
from redbot.core import Config
from redbot.core.bot import Red
from .api import INatAPI
from .obs_query import INatObsQuery
from .places import INatPlaceTable
from .projects import INatProjectTable
from .search import INatSiteSearch
from .taxon_query import INatTaxonQuery
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
        self.obs_query: INatObsQuery
        self.place_table: INatPlaceTable
        self.project_table: INatProjectTable
        self.site_search: INatSiteSearch
        self.taxon_query: INatTaxonQuery
        self._ready_event: Event
