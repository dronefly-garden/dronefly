"""Converters for command arguments."""
import argparse
import re
import shlex
from typing import NamedTuple
import discord
from redbot.core.commands import BadArgument, Context, Converter, MemberConverter
from .common import DEQUOTE, LOG
from .base_classes import (
    CompoundQuery,
    PAT_OBS_LINK,
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
            raise BadArgument("iNat member lookup is only supported in servers.")

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
        raise BadArgument("Query not understood") from None


class CompoundQueryConverter(CompoundQuery):
    """Convert query via argparse."""

    @classmethod
    async def convert(cls, ctx: Context, argument: str):
        """Parse argument into compound taxon query."""

        def detect_terms_phrases_code_id(terms_and_phrases: list):
            """Detect terms, phrases, code, and id."""
            ungroup_phrases = re.sub("'", "\\'", " ".join(list(terms_and_phrases)))
            terms = list(
                re.sub("\\\\'", "'", term) for term in shlex.split(ungroup_phrases)
            )
            phrases = [
                mat[1].split()
                for phrase in terms_and_phrases
                if (mat := re.match(r'^"(.*)"$', phrase))
            ]
            code = None
            id = None
            if not phrases and len(terms) == 1:
                if terms[0].isnumeric():
                    id = terms[0]
                elif len(terms[0]) == 4:
                    code = terms[0].upper()
            return terms, phrases, code, id

        parser = NoExitParser(description="Taxon Query Syntax", add_help=False)
        parser.add_argument("--of", nargs="+", dest="main", default=[])
        parser.add_argument("--in", nargs="+", dest="ancestor", default=[])
        parser.add_argument("--by", nargs="+", dest="user", default=[])
        parser.add_argument("--not-by", nargs="+", dest="unobserved_by", default=[])
        parser.add_argument("--id-by", nargs="+", dest="id_by", default=[])
        parser.add_argument("--from", nargs="+", dest="place", default=[])
        parser.add_argument("--rank", dest="rank", default="")
        parser.add_argument("--with", nargs="+", dest="controlled_term")
        parser.add_argument("--per", nargs="+", dest="per", default=[])
        parser.add_argument("--opt", nargs="+", dest="options", default=[])
        parser.add_argument("--in-prj", nargs="+", dest="project", default=[])

        try:
            vals = parser.parse_args(shlex.split(argument, posix=False))
        except ValueError as err:
            raise BadArgument(err.args[0])
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

        if (
            vals.main
            or vals.ancestor
            or vals.user
            or vals.place
            or vals.rank
            or vals.controlled_term
            or vals.unobserved_by
            or vals.id_by
            or vals.per
            or vals.options
            or vals.project
        ):
            main = None
            ancestor = None
            if vals.main:
                try:
                    terms, phrases, code, id = detect_terms_phrases_code_id(vals.main)
                except ValueError as err:
                    raise BadArgument(err.args[0])
                if id:
                    if ranks:
                        raise BadArgument(
                            "Taxon IDs are unique. Retry without any ranks: `sp`, `genus`, etc."
                        )
                    if vals.ancestor:
                        raise BadArgument(
                            "Taxon IDs are unique. Retry without `in <taxon2>`."
                        )
                if terms:
                    main = SimpleQuery(
                        taxon_id=id,
                        terms=terms,
                        phrases=phrases,
                        ranks=ranks,
                        code=code,
                    )
            if vals.ancestor:
                if not vals.main:
                    raise BadArgument(
                        "Missing `<taxon1>` for `<taxon1> in <taxon2>` search."
                    )
                try:
                    terms, phrases, code, id = detect_terms_phrases_code_id(
                        vals.ancestor
                    )
                except ValueError as err:
                    raise BadArgument(err.args[0])
                if terms:
                    ancestor = SimpleQuery(
                        taxon_id=id, terms=terms, phrases=phrases, ranks=[], code=code
                    )
            if vals.controlled_term:
                term_name = vals.controlled_term[0]
                term_value = " ".join(vals.controlled_term[1:])
                controlled_term = [term_name, term_value]
            else:
                controlled_term = None
            query = cls(
                main=main,
                ancestor=ancestor,
                user=" ".join(vals.user),
                place=" ".join(vals.place),
                controlled_term=controlled_term,
                unobserved_by=" ".join(vals.unobserved_by),
                id_by=" ".join(vals.id_by),
                per=" ".join(vals.per),
                project=" ".join(vals.project),
                options=vals.options,
            )
            LOG.info(repr(query))
            return query

        return argument


class NaturalCompoundQueryConverter(CompoundQueryConverter):
    """Convert query with natural language filters via argparse."""

    @classmethod
    async def convert(cls, ctx: Context, argument: str):
        """Parse argument into compound taxon query."""
        mat = re.search(PAT_OBS_LINK, argument)
        if mat and mat["url"]:
            return argument
        try:
            arg_normalized = re.sub(r"(id|not) by", r"\1-by", argument, re.I)
            arg_normalized = re.sub(r"in prj", r"in-prj", arg_normalized, re.I)
            args_normalized = shlex.split(arg_normalized, posix=False)
        except ValueError as err:
            raise BadArgument(err.args[0])
        ranks = []
        for arg in args_normalized:
            arg_lowered = arg.lower()
            if arg_lowered in RANK_KEYWORDS:
                args_normalized.remove(arg_lowered)
                ranks.append(arg_lowered)
            # FIXME: determine programmatically from parser:
            if arg_lowered in [
                "of",
                "in",
                "by",
                "not-by",
                "id-by",
                "from",
                "rank",
                "with",
                "in-prj",
                "opt",
            ]:
                args_normalized[args_normalized.index(arg_lowered)] = f"--{arg_lowered}"
        if not re.match(r"^--", args_normalized[0]):
            args_normalized.insert(0, "--of")
        if ranks:
            args_normalized.append("--rank")
            args_normalized += ranks
        argument_normalized = " ".join(args_normalized)
        return await super(NaturalCompoundQueryConverter, cls).convert(
            ctx, argument_normalized
        )
