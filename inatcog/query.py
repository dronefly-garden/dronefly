"""Module to query iNat."""
import re

from dronefly.core.query.query import (
    get_base_query_args,
    has_value,
    Query,
    QueryResponse,
)
from dronefly.core.models.controlled_terms import match_controlled_term
from pyinaturalist.models import ControlledTerm, User
from redbot.core.commands import BadArgument, Context

from .common import DEQUOTE
from .converters.base import MemberConverter


class INatQuery:
    """Query iNat for all requested entities."""

    def __init__(self, cog):
        self.cog = cog

    async def _get_user(self, user: str, **kwargs):
        try:
            response = await self.cog.api.get_users(user, **kwargs)
            if response and response["results"] and len(response["results"]) == 1:
                return User.from_json(response["results"][0])
        except (BadArgument, LookupError):
            pass
        return None

    async def get_inat_user(self, ctx: Context, user: str):
        """Get iNat user from iNat user_id, known member, or iNat login, in that order."""
        _user = None
        if user.isnumeric():
            _user = await self._get_user(user)
        if not _user:
            try:
                who = await MemberConverter.convert(ctx, re.sub(DEQUOTE, r"\1", user))
                _user = await self.cog.user_table.get_user(who.member)
            except (BadArgument, LookupError):
                pass

        if isinstance(user, str) and not _user and " " not in str(user):
            _user = await self._get_user(user, by_login_id=True)

        if not _user:
            raise LookupError("iNat member is not known or iNat login is not valid.")

        return _user

    async def _get_controlled_term(self, query_term: str, query_term_value: str):
        controlled_terms_dict = await self.cog.api.get_controlled_terms()
        controlled_terms = [
            ControlledTerm.from_json(term) for term in controlled_terms_dict["results"]
        ]
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
            await self.get_inat_user(ctx, query.user) if has_value(query.user) else None
        )
        args["unobserved_by"] = (
            await self.get_inat_user(ctx, query.unobserved_by)
            if has_value(query.unobserved_by)
            else None
        )
        args["except_by"] = (
            await self.get_inat_user(ctx, query.except_by)
            if has_value(query.except_by)
            else None
        )
        args["id_by"] = (
            await self.get_inat_user(ctx, query.id_by)
            if has_value(query.id_by)
            else None
        )
        args["controlled_term"] = (
            await self._get_controlled_term(*query.controlled_term)
            if has_value(query.controlled_term)
            else None
        )
        return QueryResponse(**args)
