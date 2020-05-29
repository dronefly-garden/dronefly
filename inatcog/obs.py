"""Module to work with iNat observations."""

import re
from typing import List, NamedTuple

from .api import WWW_BASE_URL, WWW_URL_PAT
from .photos import Photo
from .taxa import Taxon, get_taxon_fields
from .users import User

# Match observation URL or command.
PAT_OBS_LINK = re.compile(
    r"\b("
    r"(?P<url>" + WWW_URL_PAT + r"/observations/(?P<obs_id>\d+))"
    r"|(?P<cmd>obs\s+(?P<cmd_obs_id>\d+))"
    r")\b",
    re.I,
)
# Match observation URL from `obs` embed generated for observations matching a
# specific taxon_id and filtered by optional place_id and/or user_id.
PAT_OBS_TAXON_LINK = re.compile(
    r"\b(?P<url>" + WWW_URL_PAT + r"/observations"
    r"\?taxon_id=(?P<taxon_id>\d+)(&place_id=(?P<place_id>\d+))?(&user_id=(?P<user_id>\d+))?)\b",
    re.I,
)


class Obs(NamedTuple):
    """An observation."""

    taxon: Taxon or None
    community_taxon: Taxon or None
    obs_id: int
    obs_on: str
    obs_at: str
    user: User
    thumbnail: str
    images: List[Photo]
    quality_grade: str
    idents_agree: int
    idents_count: int
    faves_count: int
    comments_count: int
    description: str
    project_ids: list
    sound: str
    sounds: List[str]


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

    sounds = obs.get("sounds")
    if sounds:
        sound = sounds[0].get("file_url")
        sound_urls = [sound.get("file_url") for sound in sounds]
    else:
        sound = ""
        sound_urls = []
    project_ids = obs["project_ids"]
    non_traditional_projects = obs.get("non_traditional_projects")
    if non_traditional_projects:
        project_ids += [project["project_id"] for project in non_traditional_projects]

    return Obs(
        taxon,
        community_taxon,
        obs["id"],
        obs["observed_on_string"],
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
        sound,
        sound_urls,
    )


async def maybe_match_obs(api, content, id_permitted=False):
    """Maybe retrieve an observation from content."""
    mat = re.search(PAT_OBS_LINK, content)
    obs = url = obs_id = None
    if mat:
        obs_id = int(mat["obs_id"] or mat["cmd_obs_id"])
        url = mat["url"] or WWW_BASE_URL + "/observations/" + str(obs_id)

    if id_permitted:
        try:
            obs_id = int(content)
        except ValueError:
            pass
    if obs_id:
        results = (await api.get_observations(obs_id, include_new_projects=1))[
            "results"
        ]
        obs = get_obs_fields(results[0]) if results else None
    if obs_id and not url:
        url = WWW_BASE_URL + "/observations/" + str(obs_id)
    return (obs, url)
