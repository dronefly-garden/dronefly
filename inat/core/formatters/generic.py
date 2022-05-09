"""Generic text formatters.

Anything more complicated than plain text can be rendered in Markdown,
which is then fairly easy to render to other formats as needed.
"""
from typing import List

from ..models.taxon import Taxon, TAXON_PRIMARY_RANKS, TRINOMIAL_ABBR, RANK_LEVELS

TAXON_LIST_DELIMITER = [", ", " > "]


def format_taxon_names(
    taxa: List[Taxon], with_term=False, names_format="%s", max_len=0, hierarchy=False
):
    """Format names of taxa from matched records.

    Parameters
    ----------
    taxa: List[Taxon]
        A list of Taxon records to format, either as a comma-delimited list or
        in a hierarchy.
        - If hierarchy=True, these must be in highest to lowest rank order.
    with_term: bool, optional
        With non-common / non-name matching term in parentheses in place of common name.
    names_format: str, optional
        Format string for the name. Must contain exactly one %s.
    max_len: int, optional
        The maximum length of the return str, with ', and # more' appended if they
        don't all fit within this length.
    hierarchy: bool, optional
        If specified, formats a hierarchy list of scientific names with
        primary ranks bolded & starting on a new line, and delimited with
        angle-brackets instead of commas.

    Returns
    -------
    str
        A delimited list of formatted taxon names.
    """

    delimiter = TAXON_LIST_DELIMITER[int(hierarchy)]

    names = [
        format_taxon_name(taxon, with_term=with_term, hierarchy=hierarchy)
        for taxon in taxa
    ]

    def fit_names(names):
        names_fit = []
        # Account for space already used by format string (minus 2 for %s)
        available_len = max_len - (len(names_format) - 2)

        def more(count):
            return "and %d more" % count

        def formatted_len(name):
            return sum(len(item) + len(delimiter) for item in names_fit) + len(name)

        def overflow(name):
            return formatted_len(name) > available_len

        for name in names:
            if overflow(name):
                unprocessed = len(names) - len(names_fit)
                while overflow(more(unprocessed)):
                    unprocessed += 1
                    del names_fit[-1]
                names_fit.append(more(unprocessed))
                break
            else:
                names_fit.append(name)
        return names_fit

    if max_len:
        names = fit_names(names)

    return names_format % delimiter.join(names)


def format_taxon_name(
    taxon: Taxon, with_term=False, hierarchy=False, with_rank=True, with_common=True
):
    """Format taxon name.

    Parameters
    ----------
    with_term: bool, optional
        When with_common=True, non-common / non-name matching term is put in
        parentheses in place of common name.
    hierarchy: bool, optional
        If specified, produces a list item suitable for inclusion in the hierarchy section
        of a taxon embed. See format_taxon_names() for details.
    with_rank: bool, optional
        If specified and hierarchy=False, includes the rank for ranks higher than species.
    with_common: bool, optional
        If specified, include common name in parentheses after scientific name.

    Returns
    -------
    str
        A name of the form "Rank Scientific name (Common name)" following the
        same basic format as iNaturalist taxon pages on the web, i.e.

        - drop the "Rank" keyword for species level and lower
        - italicize the name (minus any rank abbreviations; see next point) for genus
        level and lower
        - for trinomials (must be subspecies level & have exactly 3 names to qualify),
        insert the appropriate abbreviation, unitalicized, between the 2nd and 3rd
        name (e.g. "Anser anser domesticus" -> "*Anser anser* var. *domesticus*")
    """

    if with_common:
        if with_term:
            common = (
                taxon.matched_term
                if taxon.matched_term not in (taxon.name, taxon.preferred_common_name)
                else taxon.preferred_common_name
            )
        else:
            if hierarchy:
                common = None
            else:
                common = taxon.preferred_common_name
    else:
        common = None
    name = taxon.name

    rank = taxon.rank
    rank_level = RANK_LEVELS[rank]

    if rank_level <= RANK_LEVELS["genus"]:
        name = f"*{name}*"
    if rank_level > RANK_LEVELS["species"]:
        if hierarchy:
            bold = ("\n> **", "**") if rank in TAXON_PRIMARY_RANKS else ("", "")
            name = f"{bold[0]}{name}{bold[1]}"
        elif with_rank:
            name = f"{rank.capitalize()} {name}"
    else:
        if rank in TRINOMIAL_ABBR:
            tri = name.split(" ")
            if len(tri) == 3:
                # Note: name already italicized, so close/reopen italics around insertion.
                name = f"{tri[0]} {tri[1]}* {TRINOMIAL_ABBR[rank]} *{tri[2]}"
    full_name = f"{name} ({common})" if common else name
    if not taxon.is_active:
        full_name += " :exclamation: Inactive Taxon"
    return full_name
