"""Natural language argument parser module."""
import re
import shlex

from redbot.core.commands import BadArgument

from ...core.parsers.constants import ARGPARSE_ARGS, GROUP_MACROS, MACROS, REMAINING_ARGS
from .unixlike import UnixlikeParser


class NaturalParser(UnixlikeParser):
    """Natural language query parser."""

    def parse(self, argument: str):
        """Parse natural language argument list."""
        def parse_macro(tok, macros, params={}, opts=[]):
            macro = macros.get(tok)
            if not macro:
                return (params, opts)
            _opts = [*opts]
            # Macros expanding to opt arguments can be used together, so are accumulated:
            if "opt" in macro:
                _opts.extend(macro["opt"])
            # Macros expanding to any other arguments supersede earlier values:
            _params= {**params}
            for key in macro:
                if key != "opt":
                    _params[key] = macro[key]
            return (_params, _opts)

        def parse_group(tok, groups, params={}, opts=[], expanded_tokens=[]):
            if not tok in groups:
                return (False, params, opts, expanded_tokens)

            _expanded_tokens = [*expanded_tokens]
            tok = _expanded_tokens.pop() # i.e. remove macro token to expand it
            (_params, _opts) = parse_macro(tok, GROUP_MACROS, params, opts)
            _expanded_tokens.pop() # i.e. remove --of token
            return (True, _params, _opts, _expanded_tokens)

        try:
            arg_normalized = re.sub(
                r"((^| )(id|not|except)) ?by ", r"\2\3-by ", argument, re.I
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
        # As the tokens are parsed, any that aren't deferred due to their involvement
        # in macro/group expansion are added to this list.
        expanded_tokens = []
        # Deferred params from macro/group expansion are added after all tokens parsed:
        params = {}
        # Opt params are also deferred and may be combined from multiple expansions and/or
        # explicitly specified by the user with `opt`:
        opts = []
        # - macro expansions are allowed anywhere in the taxon argument, but
        #   otherwise only when not immediately after an option token
        #   - e.g. `--of rg birds` will expand the `rg` macro, but `--from home`
        #     will not expand the `home` macro
        suppress_macro = False
        arg_count = 0

        # Group parsing state variables:
        # ------------------------------
        # Entry into group parsing mode starts with an explicit
        # or implicit "of" (i.e. unlike ordinary macros, which can happen
        # anywhere in the query):
        parsing_groups = False
        # Count non-unix-arg tokens found when parsing_groups == True:
        group_tok_count = 0
        # Group parsing already done and won't be tried again:
        groups_parsed = False
        # A group was found and expanded (i.e. functions like a taxon and
        # can't be combined with one in the same query):
        has_group = False
        # Continue to end of string to parse the remainder as opts after
        # explicit "opt" (i.e. not due to macro / group expansion)
        parsing_opts = False

        expected_args = ARGPARSE_ARGS
        for _token in tokens:
            tok = _token.lower()
            # Parsed tokens are removed from consideration to add to
            # expanded_tokens once they've been added to params and/or
            # opts. Any such deferred elements of the query are finally
            # appended after this loop has exited.
            tok_parsed = False
            argument_expected = False
            is_unix_arg = False

            if parsing_opts:
                opts.append(_token)
                continue

            if tok in expected_args:
                tok = f"--{tok}"
            if re.match(r"--", tok):
                is_unix_arg = True
                arg_count += 1
                # Every option token expects at least one argument.
                argument_expected = True
                if tok == "--of":
                    # Ignore "--of" after it is explicitly inserted.
                    expected_args = REMAINING_ARGS
                    suppress_macro = False
                    parsing_groups = not groups_parsed
                else:
                    suppress_macro = True
                # Insert at head of explicit "opt" any collected opt macro
                # expansions. This allows them to be combined in the same query,
                # e.g.
                #   `reverse birds opt observed_on=2021-06-13` ->
                #   `--of birds --opt order=asc observed_on=2021-06-13`
                if tok == "--opt":
                    parsing_opts = True
                    tok_parsed = True
            if not is_unix_arg:
                if not suppress_macro:
                    (params, opts) = parse_macro(tok, MACROS, params, opts)
                    if tok in MACROS:
                        tok_parsed = True
                # If it's an ordinary word token appearing before all other args,
                # then it's treated implicitly as first word of the "--of" argument,
                # which is inserted here.
                if (not tok_parsed) and arg_count == 0:
                    arg_count += 1
                    expanded_tokens.append("--of")
                    if "of" in params:
                        del params["of"]
                    parsing_groups = not groups_parsed
                    expected_args = REMAINING_ARGS
            if parsing_groups:
                if is_unix_arg:
                    if group_tok_count == 1:
                        # Parse the last token as a potential group:
                        last_tok = expanded_tokens[-1]
                        (has_group, params, opts, expanded_tokens) = parse_group(
                            last_tok,
                            GROUP_MACROS,
                            params,
                            opts,
                            expanded_tokens,
                        )
                        if has_group:
                            tok_parsed = True
                            # Ignore "--of" after a group macro is found
                            expected_args = REMAINING_ARGS
                        # After evaluation of the previous token, bump up the
                        # count to terminate further group expansion.
                        group_tok_count += 1
                else:
                    # Count the tokens in the taxon argument. Only a taxon
                    # argument consisting of a single token is subject to group
                    # macro expansion:
                    group_tok_count += 1
                # We exit group parsing when more than one taxon token is
                # expanded, or a new unix arg was encountered
                if group_tok_count > 1:
                    parsing_groups = False
                    groups_parsed = True
            # Append the unix option token (downcased) or unparsed ordinary word
            if (is_unix_arg and not parsing_opts) or not tok_parsed:
                expanded_tokens.append(tok if is_unix_arg else _token)
            # Macros allowed again after first non-ARGS token is consumed:
            if not argument_expected:
                suppress_macro = False

        # Finish group macro parsing when the query end is reached:
        if parsing_groups and group_tok_count == 1:
            last_tok = expanded_tokens[-1]
            (has_group, params, opts, expanded_tokens) = parse_group(
                last_tok,
                GROUP_MACROS,
                params,
                opts,
                expanded_tokens,
            )
            parsing_groups = False
            groups_parsed = True

        # Note: There can only be one of by, not by, from, or of from macros
        # until we support multiple users / places / taxa, so the last
        # user, place, or taxon given wins, superseding anything given earlier
        # in the query.
        if "by" in params:
            expanded_tokens.extend(["--by", params["by"]])
        if "not by" in params:
            expanded_tokens.extend(["--not-by", params["not by"]])
        if "from" in params:
            expanded_tokens.extend(["--from", params["from"]])
        if "of" in params:
            expanded_tokens.extend(["--of", params["of"]])
        if opts:
            expanded_tokens.extend(["--opt", *opts])

        argument_normalized = " ".join(expanded_tokens)
        return super().parse(argument_normalized)
