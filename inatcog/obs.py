"""Module to work with iNat observations."""
import datetime as dt
from operator import itemgetter
import re

from .base_classes import WWW_BASE_URL, Obs, User
from .core.parsers.url import PAT_OBS_LINK
from .photos import Photo
from .sounds import Sound
from .taxa import get_taxon_fields


def get_obs_fields(obs):
    """Get an Obs from get_observations JSON record.

    Parameters
    ----------
    obs: dict
        A JSON observation record from /v1/observations or other endpoint
        returning observations.

    Returns
    -------
    Obs
        An Obs object from the JSON results.
    """

    def count_community_id(obs, community_taxon):
        idents_count = 0
        idents_agree = 0

        ident_taxon_ids = obs["ident_taxon_ids"]

        for identification in obs["identifications"]:
            if identification["current"]:
                user_taxon_id = identification["taxon"]["id"]
                user_taxon_ids = identification["taxon"]["ancestor_ids"]
                user_taxon_ids.append(user_taxon_id)
                if community_taxon["id"] in user_taxon_ids:
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

    obs_taxon = obs.get("taxon")
    if obs_taxon:
        taxon = get_taxon_fields(obs_taxon)
    else:
        taxon = None
    obs_community_taxon = obs.get("community_taxon")
    idents_count = idents_agree = 0
    if obs_community_taxon:
        (idents_count, idents_agree) = count_community_id(obs, obs_community_taxon)
        community_taxon = get_taxon_fields(obs_community_taxon)
    else:
        idents_count = obs.get("identifications_count")
        community_taxon = None

    user = User.from_dict(obs["user"])

    photos = obs.get("photos") or []
    images = [
        Photo(
            re.sub("/square", "/original", photo.get("url")), photo.get("attribution")
        )
        for photo in photos
    ]
    if photos:
        thumbnail = photos[0].get("url")
    else:
        thumbnail = ""

    sound_recs = obs.get("sounds")
    if sound_recs:
        sounds = [
            Sound(sound.get("file_url"), sound.get("attribution"))
            for sound in sound_recs
        ]
    else:
        sounds = []
    project_ids = obs["project_ids"]
    non_traditional_projects = obs.get("non_traditional_projects")
    if non_traditional_projects:
        project_ids += [project["project_id"] for project in non_traditional_projects]
    obs_on_str = obs.get("observed_on")
    obs_on = None
    if obs_on_str:
        try:
            obs_on = dt.datetime.strptime(obs_on_str, "%Y-%m-%d")
        except ValueError:
            pass
    time_obs_str = obs.get("time_observed_at")
    time_obs = None
    if time_obs_str:
        try:
            time_obs = dt.datetime.fromisoformat(time_obs_str)
        except ValueError:
            pass

    return Obs(
        taxon,
        community_taxon,
        obs["id"],
        obs_on,
        obs["place_guess"],
        user,
        thumbnail,
        images,
        obs["quality_grade"],
        idents_agree,
        idents_count,
        obs["faves_count"],
        obs["comments_count"],
        obs["description"],
        obs["project_ids"],
        sounds,
        time_obs,
    )


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
        home = await cog.get_home(ctx)
        results = (
            await cog.api.get_observations(
                obs_id, include_new_projects=1, preferred_place_id=home
            )
        )["results"]
        obs = get_obs_fields(results[0]) if results else None
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
            observer_link = f"[{observation_count}]({observer_url}) {login}"
        else:
            observer_link = (
                f"[{observation_count} ({species_count})]({observer_url}) {login}"
            )
        return observer_link

    def format_identifier_link(identifier):
        user_id = identifier["user"]["id"]
        observation_count = identifier["count"]
        login = identifier["user"]["login"]
        identifier_url = base_url + f"&user_id={user_id}"
        observer_link = f"[{observation_count}]({identifier_url}) {login}"
        return observer_link

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
