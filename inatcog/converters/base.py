"""Converters for command arguments."""
import argparse
import re
import shlex
from typing import NamedTuple, Optional
import dateparser
import discord
from redbot.core.commands import (
    BadArgument,
    Context,
    Converter,
    MemberConverter as RedMemberConverter,
)
from inatcog.common import DEQUOTE, LOG
from inatcog.base_classes import (
    Query,
    PAT_OBS_LINK,
    TaxonQuery,
    RANK_EQUIVALENTS,
    RANK_KEYWORDS,
)


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
            match = await RedMemberConverter().convert(ctx, arg)
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


QUERY_ARGS = {
    "of": {"nargs": "+", "dest": "main", "default": []},
    "in": {"nargs": "+", "dest": "ancestor", "default": []},
    "by": {"nargs": "+", "dest": "user", "default": []},
    "not-by": {"nargs": "+", "dest": "unobserved_by", "default": []},
    "id-by": {"nargs": "+", "dest": "id_by", "default": []},
    "from": {"nargs": "+", "dest": "place", "default": []},
    "rank": {"dest": "rank", "default": ""},
    "with": {"nargs": "+", "dest": "controlled_term"},
    "per": {"nargs": "+", "dest": "per", "default": []},
    "opt": {"nargs": "+", "dest": "options", "default": []},
    "in-prj": {"nargs": "+", "dest": "project", "default": []},
    "since": {"nargs": "+", "dest": "obs_d1", "default": []},
    "until": {"nargs": "+", "dest": "obs_d2", "default": []},
    "on": {"nargs": "+", "dest": "obs_on", "default": []},
    "added-since": {"nargs": "+", "dest": "added_d1", "default": []},
    "added-until": {"nargs": "+", "dest": "added_d2", "default": []},
    "added-on": {"nargs": "+", "dest": "added_on", "default": []},
}
REMAINING_ARGS = list(QUERY_ARGS)[1:]


class QueryConverter(Query):
    """Convert query via argparse."""

    @classmethod
    # pylint: disable=unused-argument
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
            taxon_id = None
            if not phrases and len(terms) == 1:
                if terms[0].isnumeric():
                    taxon_id = terms[0]
                elif len(terms[0]) == 4:
                    code = terms[0].upper()
            return terms, phrases, code, taxon_id

        def _parse_date_arg(arg: list, prefer_dom: Optional[str] = None):
            _arg = " ".join(arg)
            if _arg.lower() == "any":
                return "any"
            settings = {"PREFER_DATES_FROM": "past"}
            if prefer_dom:
                settings["PREFER_DAY_OF_MONTH"] = prefer_dom
            return dateparser.parse(" ".join(arg), settings=settings)

        parser = NoExitParser(description="Taxon Query Syntax", add_help=False)
        for arg in QUERY_ARGS:
            parser.add_argument(f"--{arg}", **QUERY_ARGS[arg])

        try:
            vals = parser.parse_args(shlex.split(argument, posix=False))
        except ValueError as err:
            raise BadArgument(err.args[0]) from err
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
            or vals.obs_d1
            or vals.obs_d2
            or vals.obs_on
            or vals.added_d1
            or vals.added_d2
            or vals.added_on
        ):
            main = None
            ancestor = None
            if vals.main:
                try:
                    terms, phrases, code, taxon_id = detect_terms_phrases_code_id(
                        vals.main
                    )
                except ValueError as err:
                    raise BadArgument(err.args[0]) from err
                if taxon_id:
                    if ranks:
                        raise BadArgument(
                            "Taxon IDs are unique. Retry without any ranks: `sp`, `genus`, etc."
                        )
                    if vals.ancestor:
                        raise BadArgument(
                            "Taxon IDs are unique. Retry without `in <taxon2>`."
                        )
                if terms:
                    main = TaxonQuery(
                        taxon_id=taxon_id,
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
                    terms, phrases, code, taxon_id = detect_terms_phrases_code_id(
                        vals.ancestor
                    )
                except ValueError as err:
                    raise BadArgument(err.args[0]) from err
                if terms:
                    ancestor = TaxonQuery(
                        taxon_id=taxon_id,
                        terms=terms,
                        phrases=phrases,
                        ranks=[],
                        code=code,
                    )
            if vals.controlled_term:
                term_name = vals.controlled_term[0]
                term_value = " ".join(vals.controlled_term[1:])
                controlled_term = [term_name, term_value]
            else:
                controlled_term = None
            try:
                obs_d1 = _parse_date_arg(vals.obs_d1, "first")
                obs_d2 = _parse_date_arg(vals.obs_d2, "last")
                obs_on = _parse_date_arg(vals.obs_on)
                added_d1 = _parse_date_arg(vals.added_d1, "first")
                added_d2 = _parse_date_arg(vals.added_d2, "last")
                added_on = _parse_date_arg(vals.added_on)
            except RuntimeError as err:
                raise BadArgument(err) from err
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
                obs_d1=obs_d1,
                obs_d2=obs_d2,
                obs_on=obs_on,
                added_d1=added_d1,
                added_d2=added_d2,
                added_on=added_on,
            )
            LOG.info(repr(query))
            return query

        return argument


QUERY_MACROS = {
    "rg": {"opt": ["quality_grade=research"]},
    "nid": {"opt": ["quality_grade=needs_id"]},
    "oldest": {"opt": ["order=asc", "order_by=observed_on"]},
    "newest": {"opt": ["order=desc", "order_by=observed_on"]},
    "reverse": {"opt": ["order=asc"]},
    # Because there are no iconic taxa for these three taxa, they must be specifically
    # excluded in order to match only actual unknowns (Bacteria, Archaea, & Viruses):
    "unknown": {"opt": ["iconic_taxa=unknown", "without_taxon_id=67333,151817,131236"]},
    "my": {"by": "me"},
    "home": {"from": "home"},
}


class NaturalQueryConverter(QueryConverter):
    """Convert query with natural language filters via argparse."""

    @classmethod
    async def convert(cls, ctx: Context, argument: str):
        """Parse argument into compound taxon query."""
        mat = re.search(PAT_OBS_LINK, argument)
        if mat and mat["url"]:
            return argument
        try:
            arg_normalized = re.sub(
                r"((^| )(id|not)) ?by ", r"\2\3-by ", argument, re.I
            )
            arg_normalized = re.sub(
                r"((^| )in ?prj) ", r"\2in-prj ", arg_normalized, re.I
            )
            arg_normalized = re.sub(
                r"((^| )added ?(on|since|until)) ", r"\2added-\3 ", arg_normalized, re.I
            )
            tokens = shlex.split(arg_normalized, posix=False)
        except ValueError as err:
            raise BadArgument(err.args[0]) from err
        ranks = []
        opts = []
        macro_by = ""
        macro_from = ""
        expanded_tokens = []
        # - rank keywords & macro expansions are allowed anywhere in the
        #   taxon argument, but otherwise only when not immediately after
        #   an option token
        #   - e.g. `--of rg birds` or `--of ssp mallard` will expand
        #     the `rg` macro and `ssp` rank keyword, but `--from home`
        #     will not expand the `home` macro
        suppress_macro = False
        arg_count = 0
        expected_args = QUERY_ARGS
        for _token in tokens:
            tok = _token.lower()
            argument_expected = False

            if tok in expected_args:
                tok = f"--{tok}"
            if re.match(r"--", tok):
                arg_count += 1
                # Every option token expects at least one argument.
                argument_expected = True
                if tok == "--of":
                    # Ignore "--of" after it is explicitly inserted.
                    expected_args = REMAINING_ARGS
                    suppress_macro = False
                else:
                    suppress_macro = True
                # Insert at head of explicit "opt" or "rank" any collected
                # ranks or opt macro expansions. This allows them to be
                # combined in the same query, e.g.
                #   `reverse birds opt observed_on=2021-06-13` ->
                #   `--of birds --opt order=asc observed_on=2021-06-13`
                # or
                #   `ssp ducks rank sp` -> `--of ducks --rank ssp sp`
                #   - not super useful, but handled for consistency, as
                #     rank expansion is a special kind of macro expansion
                if tok == "--opt" and opts:
                    expanded_tokens.extend(["--opt", *opts])
                    opts = []
                    continue
                if tok == "--rank" and ranks:
                    expanded_tokens.extend(["--rank", *ranks])
                    ranks = []
                    continue
                # Discard any prior macro expansions of these; see note below
                if tok == "--by":
                    macro_by = ""
                if tok == "--from":
                    macro_from = ""
            if not suppress_macro:
                if tok in RANK_KEYWORDS:
                    ranks.append(tok)
                    continue
                if tok in QUERY_MACROS:
                    macro = QUERY_MACROS[tok]
                    if macro:
                        # Collect any expansions and continue:
                        _macro_opt_args = macro.get("opt")
                        if _macro_opt_args:
                            opts.extend(_macro_opt_args)
                        _macro_by = macro.get("by")
                        if _macro_by:
                            macro_by = _macro_by
                        _macro_from = macro.get("from")
                        if _macro_from:
                            macro_from = _macro_from
                        continue
            # If it's an ordinary word token appearing before all other args,
            # then it's treated implicitly as first word of the "--of" argument,
            # which is inserted here.
            if arg_count == 0:
                arg_count += 1
                expanded_tokens.append("--of")
                expected_args = REMAINING_ARGS
            # Append the ordinary word token:
            expanded_tokens.append(tok)
            # Macros allowed again after first non-ARGS token is consumed:
            if not argument_expected:
                suppress_macro = False

        # Handle collected arguments that were not already
        # inserted into filtered_args above by appending them:
        if ranks:
            expanded_tokens.extend(["--rank", *ranks])
        if opts:
            expanded_tokens.extend(["--opt", *opts])
        # Note: There can only be one of macro_by or macro_from until we support
        # multiple users / places, so the last user or place given wins,
        # superseding anything given earlier in the query.
        if macro_by:
            expanded_tokens.extend(["--by", macro_by])
        if macro_from:
            expanded_tokens.extend(["--from", macro_from])
        # Treat any unexpanded args before the first option keyword
        # argument as implicit "--of" option arguments:
        if not re.match(r"^--", expanded_tokens[0]):
            expanded_tokens.insert(0, "--of")
        argument_normalized = " ".join(expanded_tokens)
        return await super(NaturalQueryConverter, cls).convert(ctx, argument_normalized)
