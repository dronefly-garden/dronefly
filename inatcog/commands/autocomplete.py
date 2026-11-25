import asyncio
import logging
import re
import sqlite3
import time
from typing import List, Optional

from dronefly.core.formatters import format_taxon_name
from dronefly.core.parsers.constants import VIRTUAL_TAXA
from dronefly.miner import taxon_autocomplete

from discord import app_commands, Interaction
from pyinaturalist import RANKS, RANK_EQUIVALENTS, Taxon

LANGUAGE_CODE_PAT = re.compile(r"^[a-z]{2}(_[a-z]{2})? ", re.I)

logger = logging.getLogger("red.dronefly." + __name__)


async def discord_taxon_autocomplete(
    cog,
    interaction: Interaction,
    current: str,
    group_taxa: Optional[dict] = {},
) -> List[app_commands.Choice[str]]:
    def fetch_taxon_choices(current: str):
        """Return choices from fast FTS taxon autocomplete search

        - English common names by default, overridden by language code as the first word.
        - Filtered on rank if the first word (or second if language specified) is a rank.
        """
        _current = current.strip()
        if not _current:
            return []

        strict_language = False
        mat = re.match(LANGUAGE_CODE_PAT, _current)
        if mat:
            language = mat[0].strip()
            _current = LANGUAGE_CODE_PAT.sub("", _current).strip()
            strict_language = True
        else:
            language = "en"

        words = _current.split()
        rank = None
        if len(words) > 1:
            first_word = words[0].lower()
            if first_word in RANKS:
                rank = first_word
            else:
                rank = RANK_EQUIVALENTS.get(first_word)

            if rank:
                words.remove(first_word)
                _current = " ".join(words)

        taxa = []
        # if a rank is specified, group keywords are omitted from the results as
        # paraphyletic groups don't have a rank.
        if group_taxa and len(words) == 1 and not rank:
            token = _current.lower()
            _taxa = [
                Taxon(
                    **VIRTUAL_TAXA[key]["taxon_params"],
                    is_active=True,
                    uuid=key,
                    matched_term=key,
                )
                for key in group_taxa.keys()
                if token == key[: len(token)]
            ]
            if _taxa:
                taxa.extend(_taxa)

        if len(_current) < 3:
            return []

        taxon_autocompleter = cog.taxon_autocomplete_manager.get_autocompleter()
        if not taxon_autocompleter:
            return []

        _taxa = taxon_autocomplete(
            _current,
            autocompleter=taxon_autocompleter,
            language=language,
            rank=rank,
            strict_language=strict_language,
        )
        if _taxa:
            taxa.extend(_taxa)

        if taxa:
            return [
                app_commands.Choice(
                    name=format_taxon_name(taxon, with_term=True, with_italics=False),
                    value=f"id:{taxon.id or taxon.uuid}",
                )
                for taxon in taxa[:10]
            ]
        return []

    start_time = time.perf_counter()
    reason = "autocomplete not configured"
    response = []

    if cog.taxon_autocomplete_manager and current:
        try:
            response = await asyncio.wait_for(
                cog.bot.loop.run_in_executor(None, fetch_taxon_choices, current),
                timeout=2.5,
            )
        except (
            sqlite3.OperationalError,
            sqlite3.InterfaceError,
            sqlite3.DatabaseError,
        ) as e:
            logger.error("Database error during autocomplete for '%s': %s", current, e)
            reason = "autocomplete offline during rebuild"
        except TimeoutError:
            reason = "autocomplete timed out"

        if not response and current and reason != "autocomplete not configured":
            response = [
                app_commands.Choice(
                    name=f"{current} ({reason})",
                    value=current,
                )
            ]

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        f'autocompleted "{current}" in {elapsed_ms:.2f}ms (matched {len(response)})'
    )
    return response
