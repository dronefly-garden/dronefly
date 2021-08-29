"""Module for URL parsing"""
import re

# Match any iNaturalist partner URL
# See https://www.inaturalist.org/pages/network
WWW_URL_PAT = (
    r"https?://("
    r"((www|colombia|costarica|panama|ecuador|israel|greece|uk|guatemala)\.)?inaturalist\.org"
    r"|inaturalist\.ala\.org\.au"
    r"|(www\.)?("
    r"inaturalist\.(ca|lu|nz|se)"
    r"|naturalista\.mx"
    r"|biodiversity4all\.org"
    r"|argentinat\.org"
    r"|inaturalist\.laji\.fi"
    r")"
    r")"
)
PAT_TAXON_LINK = re.compile(
    r"\b(?P<url>" + WWW_URL_PAT + r"/taxa/(?P<taxon_id>\d+))\b", re.I
)
