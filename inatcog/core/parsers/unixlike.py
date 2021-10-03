"""Unixlike argument parser module."""
import argparse
import re
from typing import Optional

import shlex
import dateparser

from ..models.taxon import RANK_EQUIVALENTS
from ..parsers.url import PAT_TAXON_LINK
from ..query.query import Query, TaxonQuery
from .constants import ARGPARSE_ARGS


class NoExitParser(argparse.ArgumentParser):
    """Handle default error as RuntimeError, not sys.exit.

    Workaround for Python 3.8 not yet having exit_on_error, which was only added in Python 3.9.
    """

    def error(self, message):
        raise ValueError("Argument not understood") from None


# TODO: consider using a subparser for of and in to make --in invalid
# unless paired with --of
# - see https://docs.python.org/3/library/argparse.html#sub-commands
# TODO: handle macros here instead of in natural query parser
# TODO: handle opt value here instead of in query


def _detect_terms_phrases_code_id(terms_and_phrases: list):
    ungroup_phrases = re.sub("'", "\\'", " ".join(list(terms_and_phrases)))
    terms = list(re.sub("\\\\'", "'", term) for term in shlex.split(ungroup_phrases))
    phrases = [
        mat[1].split()
        for phrase in iter(terms_and_phrases)
        if (mat := re.match(r'^"(.*)"$', phrase))
    ]
    code = None
    taxon_id = None
    if not phrases and len(terms) == 1:
        if terms[0].isnumeric():
            taxon_id = terms[0]
        elif len(terms[0]) == 4:
            code = terms[0].upper()
        else:
            mat = re.search(PAT_TAXON_LINK, terms[0])
            if mat and mat["taxon_id"]:
                taxon_id = mat["taxon_id"]

    return terms, phrases, code, taxon_id


def _parse_date_arg(arg: list, prefer_dom: Optional[str] = None):
    _arg = " ".join(arg)
    if _arg.lower() == "any":
        return "any"
    settings = {"PREFER_DATES_FROM": "past"}
    if prefer_dom:
        settings["PREFER_DAY_OF_MONTH"] = prefer_dom
    return dateparser.parse(" ".join(arg), settings=settings)


class UnixlikeParser:
    """Unixlike argument parser."""

    def __init__(self, return_class=Query):
        self.parser = NoExitParser(description="Unixlike Query", add_help=False)
        self.return_class = return_class
        for arg in ARGPARSE_ARGS:
            self.parser.add_argument(f"--{arg}", **ARGPARSE_ARGS[arg])

    def parse(self, argument: str):
        """Parse unixlike argument list with argparse."""
        # - https://docs.python.org/3/library/argparse.html#action
        vals = self.parser.parse_args(shlex.split(argument, posix=False))

        # TODO: implement the following as argparse.Action subclasses, so that all
        # we need to do is the parse_args call above, and return the result.
        ranks = []
        if vals.ranks:
            ranks = list(
                [
                    RANK_EQUIVALENTS[rank] if rank in RANK_EQUIVALENTS else rank
                    for rank in vals.ranks
                ]
            )

        if any(vars(vals).values()):
            main = None
            ancestor = None
            if vals.main:
                terms, phrases, code, taxon_id = _detect_terms_phrases_code_id(
                    vals.main
                )
                if taxon_id:
                    if ranks:
                        raise ValueError(
                            "Taxon IDs are unique. Retry without any ranks: `sp`, `genus`, etc."
                        )
                    if vals.ancestor:
                        raise ValueError(
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
                    raise ValueError(
                        "Missing `<taxon1>` for `<taxon1> in <taxon2>` search."
                    )
                terms, phrases, code, taxon_id = _detect_terms_phrases_code_id(
                    vals.ancestor
                )
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
                raise ValueError(err) from err

            # TODO: in Query itself, accept dict & list arguments, translating
            # them internally into TaxonQuery and str if that's what is desired.
            # - alternatively, have the Action subclasses construct the desired
            #   types directly
            return self.return_class(
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
        return None
