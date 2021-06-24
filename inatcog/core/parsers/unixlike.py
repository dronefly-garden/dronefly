"""Unixlike argument parser module."""
import argparse
import re
from typing import Optional

import shlex
import dateparser

from ..models.taxon import RANK_EQUIVALENTS
from ..query.query import Query, TaxonQuery


class NoExitParser(argparse.ArgumentParser):
    """Handle default error as RuntimeError, not sys.exit.

    Workaround for Python 3.8 not yet having exit_on_error, which was only added in Python 3.9.
    """

    def error(self, message):
        raise RuntimeError("Argument not understood") from None


# TODO: consider using a subparser for of and in to make --in invalid
# unless paired with --of
# - see https://docs.python.org/3/library/argparse.html#sub-commands
ARGPARSE_ARGS = {
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
# TODO: handle macros here instead of in natural query parser
MACROS = {
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
    "faves": {"opt": ["popular", "order_by=votes"]},
}
# TODO: handle opt value here instead of in query
VALID_OBS_OPTS = [
    "captive",
    "day",
    "endemic",
    "iconic_taxa",
    "id",
    "identified",
    "introduced",
    "month",
    "native",
    "not_id",
    "order",
    "order_by",
    "out_of_range",
    "page",
    "pcid",
    "photos",
    "popular",
    "quality_grade",
    "reviewed",
    "sounds",
    "threatened",
    "verifiable",
    "without_taxon_id",
    "year",
]


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
