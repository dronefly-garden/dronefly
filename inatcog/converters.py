"""Converters for command arguments."""
import argparse
import re
import shlex
from typing import NamedTuple
import discord
from redbot.core.commands import BadArgument, Context, Converter, MemberConverter
from .common import DEQUOTE
from .taxon_classes import (
    CompoundQuery,
    SimpleQuery,
    RANK_EQUIVALENTS,
    RANK_KEYWORDS,
)


class ContextMemberConverter(NamedTuple):
    """Context-aware member converter."""

    member: discord.Member

    @classmethod
    async def convert(cls, ctx: Context, arg: str):
        """Find best match for member from recent messages."""
        if not ctx.guild:
            return

        # Handle special 'me' user:
        if arg.lower() == "me":
            return cls(ctx.author)

        # Prefer exact match:
        try:
            match = await MemberConverter().convert(ctx, arg)
            return cls(match)
        except BadArgument:
            match = None

        pat = re.escape(arg)

        # Try partial match on name or nick from recent messages for this guild.
        cached_members = {
            str(msg.author.name): msg.author
            for msg in ctx.bot.cached_messages
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
        return await ContextMemberConverter.convert(ctx, dequoted)


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
        raise BadArgument() from None


class CompoundQueryConverter(CompoundQuery):
    """Convert query via argparse."""

    @classmethod
    async def convert(cls, ctx: Context, argument: str):
        """Parse argument into compound taxon query."""

        def detect_terms_phrases_code(terms_and_phrases: list):
            """Detect terms, phrases, and code."""
            terms = shlex.split(" ".join(list(terms_and_phrases)))
            phrases = [
                mat[1].split()
                for phrase in terms_and_phrases
                if (mat := re.match(r'^"(.*)"$', phrase))
            ]
            code = None
            if not phrases and len(terms) == 1 and len(terms[0]) == 4:
                code = terms[0].upper()
            return terms, phrases, code

        parser = NoExitParser(description="Taxon Query Syntax", add_help=False)
        parser.add_argument("--of", nargs="+", dest="main", default=[])
        parser.add_argument("--in", nargs="+", dest="ancestor", default=[])
        parser.add_argument("--by", nargs="+", dest="user", default=[])
        parser.add_argument("--from", nargs="+", dest="place", default=[])
        parser.add_argument("--rank", dest="rank", default="")

        vals = parser.parse_args(shlex.split(argument, posix=False))
        ranks = []
        if vals.rank:
            parsed_ranks = shlex.shlex(vals.rank)
            parsed_ranks.whitespace += ","
            parsed_ranks.whitespace_split = True
            ranks_with_equivalents = list(parsed_ranks)
            ranks = list(
                [
                    RANK_EQUIVALENTS[rank] if rank in RANK_EQUIVALENTS else rank
                    for rank in ranks_with_equivalents
                ]
            )

        if vals.main or vals.ancestor or vals.user or vals.place:
            terms, phrases, code = detect_terms_phrases_code(vals.main)
            main = SimpleQuery(
                taxon_id=None, terms=terms, phrases=phrases, ranks=ranks, code=code,
            )
            if vals.ancestor:
                terms, phrases, code = detect_terms_phrases_code(vals.ancestor)
                ancestor = SimpleQuery(
                    taxon_id=None, terms=terms, phrases=phrases, code=code
                )
            else:
                ancestor = None
            return cls(
                main=main,
                ancestor=ancestor,
                user=" ".join(vals.user),
                place=" ".join(vals.place),
                group_by="",
            )

        return argument


class NaturalCompoundQueryConverter(CompoundQueryConverter):
    """Convert query with natural language filters via argparse."""

    @classmethod
    async def convert(cls, ctx: Context, argument: str):
        """Parse argument into compound taxon query."""
        args_normalized = shlex.split(argument, posix=False)
        if not re.match(r"^--", args_normalized[0]):
            args_normalized.insert(0, "--of")
        ranks = []
        for arg in args_normalized:
            arg_lowered = arg.lower()
            if arg_lowered in RANK_KEYWORDS:
                args_normalized.remove(arg_lowered)
                ranks.append(arg_lowered)
            # FIXME: determine programmatically from parser:
            if arg_lowered in ["of", "in", "by", "from", "rank"]:
                args_normalized[args_normalized.index(arg_lowered)] = f"--{arg_lowered}"
        if ranks:
            args_normalized.append("--rank")
            args_normalized += ranks
        argument_normalized = " ".join(args_normalized)
        await ctx.send(argument_normalized)
        return await super(NaturalCompoundQueryConverter, cls).convert(
            ctx, argument_normalized
        )
