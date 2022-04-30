"""Module to access iNaturalist API.

- Note: Most methods use aiohttp directly, whereas some now use pyinaturalist. Please note
  that for each of these we're working on moving from homegrown approaches to built-in
  capabilities in pyinaturalist for:
  - caching
  - rate-limiting
- Until migration to pyinaturalist is complete, mismatches between the two approaches might
  lead to:
  - any old code that depends on specific caching behaviours may not work correctly with
    new pyinaturalist-based replacements
  - there's an outside chance that rate limits may be exceeded, since neither rate-limiter
    is aware of the rate buckets collected by the other.
- Therefore, take care to add transitional code that mixes the two underlying libraries
  sparingly, and in particular:
  - prefer adding new methods over modifying existing ones to use pyinaturalist
  - focus on methods for commands that are infrequently called to reduce the
    probability of rate limits being exceeded
"""
from functools import partial
import logging
from time import time

from pyinaturalist import get_taxa_autocomplete

# FIXME: learn how Logging hierarchical loggers work and implement
LOG = logging.getLogger("red.dronefly.inatcog")

API_BASE_URL = "https://api.inaturalist.org"


class INatAPI:
    """Access the iNat API and assets via (api|static).inaturalist.org."""

    def __init__(self):
        # pylint: disable=unused-argument
        self.request_time = time()

    async def _pyinaturalist_endpoint(self, endpoint, ctx, *args, **kwargs):
        if "access_token" in kwargs:
            safe_kwargs = {**kwargs}
            safe_kwargs["access_token"] = "***REDACTED***"
        else:
            safe_kwargs = kwargs
        LOG.info(
            "_pyinaturalist_endpoint(%s, %s, %s)",
            endpoint.__name__,
            repr(args),
            repr(safe_kwargs),
        )

        return await ctx.bot.loop.run_in_executor(
            None, partial(endpoint, *args, **kwargs)
        )

    async def get_taxa_autocomplete(self, ctx, **kwargs):
        """Get taxa using autocomplete."""
        # - TODO: support user settings for home place, language
        return await self._pyinaturalist_endpoint(get_taxa_autocomplete, ctx, **kwargs)
