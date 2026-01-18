"""Module to query iNat."""
from dronefly.core.query.query import (
    get_base_query_args,
    has_value,
    Query,
    QueryResponse,
)
from dronefly.core.models.controlled_terms import match_controlled_term
from redbot.core.commands import Context

from .users import get_inat_user


class INatQuery:
    """Query iNat for all requested entities."""

    def __init__(self, cog):
        self.cog = cog

    async def _get_controlled_term(self, ctx, query_term: str, query_term_value: str):
        async with self.cog.inat_client.set_ctx_from_user(ctx) as client:
            controlled_terms = await client.annotations.async_all()
        controlled_term = match_controlled_term(
            controlled_terms, query_term, query_term_value
        )
        return controlled_term

    async def get(
        self, ctx: Context, query: Query, scientific_name=False, locale=None, **kwargs
    ):
        """Get all requested iNat entities."""
        args = get_base_query_args(query)

        args["project"] = (
            await self.cog.project_table.get_project(
                ctx.guild, query.project, ctx.author
            )
            if has_value(query.project)
            else None
        )
        args["place"] = (
            await self.cog.place_table.get_place(ctx.guild, query.place, ctx.author)
            if has_value(query.place)
            else None
        )
        taxon_params = {
            "scientific_name": scientific_name,
            "locale": locale,
        }
        if args["place"]:
            taxon_params["preferred_place_id"] = args["place"].id
        args["taxon"] = (
            await self.cog.taxon_query.maybe_match_taxon_compound(
                ctx, query, **taxon_params
            )
            if has_value(query.main)
            else None
        )
        args["user"] = (
            await get_inat_user(ctx, query.user) if has_value(query.user) else None
        )
        args["unobserved_by"] = (
            await get_inat_user(ctx, query.unobserved_by)
            if has_value(query.unobserved_by)
            else None
        )
        args["except_by"] = (
            await get_inat_user(ctx, query.except_by)
            if has_value(query.except_by)
            else None
        )
        args["id_by"] = (
            await get_inat_user(ctx, query.id_by) if has_value(query.id_by) else None
        )
        args["controlled_term"] = (
            await self._get_controlled_term(ctx, *query.controlled_term)
            if has_value(query.controlled_term)
            else None
        )
        args["per"] = query.per if has_value(query.per) else None
        return QueryResponse(**args)
