"""Module to work with iNat observations."""
from operator import itemgetter
import re

from dronefly.core.formatters.constants import WWW_BASE_URL
from dronefly.core.parsers.url import PAT_OBS_LINK
from pyinaturalist.models import Observation

from .utils import get_home


def obs_count_community_id(obs):
    idents_count = 0
    idents_agree = 0

    ident_taxon_ids = []
    # TODO: when pyinat supports ident_taxon_ids, this can be removed.
    for ident in obs.identifications:
        if ident.taxon:
            for ancestor_id in ident.taxon.ancestor_ids:
                if ancestor_id not in ident_taxon_ids:
                    ident_taxon_ids.append(ancestor_id)
            if ident.taxon.id not in ident_taxon_ids:
                ident_taxon_ids.append(ident.taxon.id)
    for identification in obs.identifications:
        if identification.current:
            user_taxon_id = identification.taxon.id
            user_taxon_ids = identification.taxon.ancestor_ids
            user_taxon_ids.append(user_taxon_id)
            if obs.community_taxon_id in user_taxon_ids:
                if user_taxon_id in ident_taxon_ids:
                    # Count towards total & agree:
                    idents_count += 1
                    idents_agree += 1
                else:
                    # Neither counts for nor against
                    pass
            else:
                # Maverick counts against:
                idents_count += 1

    return (idents_count, idents_agree)

async def maybe_match_obs(cog, ctx, content, id_permitted=False):
    """Maybe retrieve an observation from content."""
    mat = re.search(PAT_OBS_LINK, content)
    obs = url = obs_id = None
    if mat:
        obs_id = int(mat["obs_id"])
        url = mat["url"] or WWW_BASE_URL + "/observations/" + str(obs_id)

    if id_permitted:
        try:
            obs_id = int(content)
        except ValueError:
            pass
    if obs_id:
        home = await get_home(ctx)
        results = (
            await cog.api.get_observations(
                obs_id, include_new_projects=1, preferred_place_id=home
            )
        )["results"]
        obs = Observation.from_json(results[0]) if results else None
    if obs_id and not url:
        url = WWW_BASE_URL + "/observations/" + str(obs_id)
    return (obs, url)


def get_formatted_user_counts(
    user_counts: dict, base_url: str, species_only: bool = False, view: str = "obs"
):
    """Format per user observation & species counts."""

    def format_observer_link(observer, species_only):
        user_id = observer["user_id"]
        species_count = observer["species_count"]
        observation_count = observer["observation_count"]
        login = observer["user"]["login"]
        observer_url = base_url + f"&user_id={user_id}"
        if species_only:
            observer_link = f"[{observation_count:,}]({observer_url}) {login}"
        else:
            observer_link = (
                f"[{observation_count:,} ({species_count:,})]({observer_url}) {login}"
            )
        return observer_link

    def format_identifier_link(identifier):
        user_id = identifier["user"]["id"]
        observation_count = identifier["count"]
        login = identifier["user"]["login"]
        identifier_url = base_url + f"&ident_user_id={user_id}&not_user_id={user_id}"
        identifier_link = f"[{observation_count:,}]({identifier_url}) {login}"
        return identifier_link

    if view == "ids":
        identifier_links = [
            "{}) {}".format(rank + 1, format_identifier_link(ider))
            for rank, ider in enumerate(user_counts["results"])
        ]
        return identifier_links

    if not species_only and view == "spp":
        sorted_observers = sorted(
            user_counts["results"],
            key=itemgetter("species_count", "observation_count"),
            reverse=True,
        )
    else:
        sorted_observers = user_counts["results"]
    observer_links = [
        "{}) {}".format(rank + 1, format_observer_link(observer, species_only))
        for rank, observer in enumerate(sorted_observers)
    ]
    return observer_links
