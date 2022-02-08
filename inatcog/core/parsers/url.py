"""Module for URL parsing"""
import re

# Match any iNaturalist partner URL
# See https://www.inaturalist.org/pages/network
# - each partner domain matches one of the four schemes below
WWW_URL_PAT = (
    r"https?://("
    # <partner>.inaturalist.org and the main site [www.]inaturalist.org
    r"((www|colombia|costarica|panama|ecuador|israel|greece|uk|guatemala)\.)?inaturalist\.org"
    # inaturalist.<partner>.<tld>
    r"|inaturalist\.(ala\.org\.au|laji\.fi|mma\.gob\.cl)"
    r"|(www\.)?("
    # [www.]inaturalist.<tld>
    r"inaturalist\.(ca|lu|nz|se)"
    # [www.]<partner>.<tld>
    r"|naturalista\.(mx|uy)"
    r"|biodiversity4all\.org"
    r"|argentinat\.org"
    r")"
    r")"
)
PAT_TAXON_LINK = re.compile(
    r"\b(?P<url>" + WWW_URL_PAT + r"/taxa/(?P<taxon_id>\d+))\b", re.I
)
STATIC_URL_PAT = (
    r"https?://(static\.inaturalist\.org|inaturalist-open-data\.s3\.amazonaws\.com)"
)

# Match observation URL or command.
PAT_OBS_LINK = re.compile(
    r"\b(?P<url>" + WWW_URL_PAT + r"/observations/(?P<obs_id>\d+))\b", re.I
)
# Match observation URL from `obs` embed generated for observations matching a
# specific taxon_id and filtered by optional place_id and/or user_id.
PAT_OBS_TAXON_LINK = re.compile(
    r"\b(?P<url>" + WWW_URL_PAT + r"/observations"
    r"\?taxon_id=(?P<taxon_id>\d+)(&place_id=(?P<place_id>\d+))?(&user_id=(?P<user_id>\d+))?)\b",
    re.I,
)

QUERY_PAT = r"\??(?:&?[^=&]*=[^=&]*)*"
PAT_OBS_QUERY = re.compile(
    r"(?P<url>" + WWW_URL_PAT + r"/observations" + QUERY_PAT + ")"
)
MARKDOWN_LINK = re.compile(r"\[.*?\]\((?P<url>.*?)\)")

# Match place link from any partner site.
PAT_PLACE_LINK = re.compile(
    r"\b(?P<url>" + WWW_URL_PAT + r"/places"
    r"/((?P<place_id>\d+)|(?P<place_slug>[a-z][-_a-z0-9]{2,39}))"
    r")\b",
    re.I,
)
# Match project link from any partner site.
PAT_PROJECT_LINK = re.compile(
    r"\b(?P<url>" + WWW_URL_PAT + r"/projects"
    r"/((?P<project_id>\d+)|(?P<project_slug>[a-z][-_a-z0-9]{2,39}))"
    r")\b",
    re.I,
)
# Match user profile link from any partner site.
PAT_USER_LINK = re.compile(
    r"\b(?P<url>" + WWW_URL_PAT + r"/(people|users)"
    r"/((?P<user_id>\d+)|(?P<login>[a-z][-_a-z0-9]{2,39}))"
    r")\b",
    re.I,
)
