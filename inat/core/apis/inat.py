"""Module to access iNaturalist API."""
from functools import partial
import logging
from time import time

from pyinaturalist import get_taxa_autocomplete

# FIXME: learn how Logging hierarchical loggers work and implement
LOG = logging.getLogger("red.dronefly.inatcog")


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
