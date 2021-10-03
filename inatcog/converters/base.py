"""Converters for command arguments."""
import argparse
import re
from typing import NamedTuple

import discord
from discord.ext.commands import MemberConverter as DiscordMemberConverter
from redbot.core.commands import (
    BadArgument,
    Context,
    Converter,
)

from ..common import DEQUOTE
from ..core.parsers.natural import NaturalParser
from ..core.query.query import Query


class MemberConverter(NamedTuple):
    """Context-aware member converter."""

    member: discord.Member

    @classmethod
    async def convert(cls, ctx: Context, arg: str):
        """Find best match for member from recent messages."""
        if not ctx.guild:
            raise BadArgument("iNat member lookup is only supported in servers.")

        # Handle special 'me' user:
        if arg.lower() == "me":
            return cls(ctx.author)

        # Prefer exact match:
        try:
            match = await DiscordMemberConverter().convert(ctx, arg)
            return cls(match)
        except BadArgument:
            match = None

        pat = re.escape(arg)

        # Try partial match on name or nick from recent messages for this guild.
        cached_members = {
            str(msg.author.name): msg.author
            for msg in reversed(ctx.bot.cached_messages)
            if not msg.author.bot
            and ctx.guild == msg.guild
            and ctx.guild.get_member(msg.author.id)
        }
        matches = [
            cached_members[name]
            for name in cached_members
            if re.match(pat, name, re.I)
            or (
                cached_members[name].nick
                and re.match(pat, cached_members[name].nick, re.I)
            )
        ]
        # First match is considered the best match (i.e. more recently active)
        match = ctx.guild.get_member(matches[0].id) if matches else None
        if match:
            return cls(match)

        # Otherwise no partial match from context, & no exact match
        raise BadArgument(
            "No recently active member found. Try exact username or nickname."
        )


class QuotedContextMemberConverter(Converter):
    """Convert possibly quoted arg by dropping double-quotes."""

    async def convert(self, ctx, argument):
        dequoted = re.sub(DEQUOTE, r"\1", argument)
        return await MemberConverter.convert(ctx, dequoted)


class InheritableBoolConverter(Converter):
    """Convert truthy or 'inherit' to True, False, or None (inherit)."""

    async def convert(self, ctx, argument):
        lowered = argument.lower()
        if lowered in ("yes", "y", "true", "t", "1", "enable", "on"):
            return True
        if lowered in ("no", "n", "false", "f", "0", "disable", "off"):
            return False
        if lowered in ("i", "inherit", "inherits", "inherited"):
            return None
        raise BadArgument(f'{argument} is not a recognized boolean option or "inherit"')


class NoExitParser(argparse.ArgumentParser):
    """Handle default error as bad argument, not sys.exit."""

    def error(self, message):
        raise BadArgument("Query not understood") from None


class NaturalQueryConverter(Query):
    """Convert query with natural language filters via argparse."""

    @classmethod
    # pylint: disable=unused-argument
    async def convert(cls, ctx: Context, argument: str):
        """Parse argument into compound taxon query."""

        try:
            parser = NaturalParser(return_class=cls)
            return parser.parse(argument)
        except ValueError as err:
            raise BadArgument(str(err)) from err
