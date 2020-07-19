"""Module for API classes and constants."""

API_BASE_URL = "https://api.inaturalist.org"
WWW_BASE_URL = "https://www.inaturalist.org"
# Match any iNaturalist partner URL
# See https://www.inaturalist.org/pages/network
WWW_URL_PAT = (
    r"https?://("
    r"((www|colombia|panama|ecuador|israel)\.)?inaturalist\.org"
    r"|inaturalist\.ala\.org\.au"
    r"|(www\.)?("
    r"inaturalist\.(ca|nz)"
    r"|naturalista\.mx"
    r"|biodiversity4all\.org"
    r"|argentinat\.org"
    r"|inaturalist\.laji\.fi"
    r")"
    r")"
)
