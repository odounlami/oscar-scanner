"""Central registry of job sources.

A source stays in the registry even when temporarily disabled. This makes it
possible to pause a blocked source without losing its history/configuration.
"""

SOURCES = [
    {
        "name": "JobBenin",
        "url": "https://jobbenin.com/index.php/offres/categorie/informatique",
        "active": True,
        "extractor": "jobbenin",
    },
    {
        "name": "EmploiBenin",
        "url": "https://www.emploibenin.com/recherche-jobs-benin/informatique",
        "active": False,
        "extractor": "emploibenin",
        "reason": "Temporarily paused: Cloudflare anti-bot blocks requests.",
    },
    {
        "name": "GoAfricaOnline",
        "url": "https://www.goafricaonline.com/bj/emploi",
        "active": True,
        "extractor": "goafrica",
    },
]


def active_sources():
    """Return only sources explicitly enabled in the registry."""
    return [source for source in SOURCES if source.get("active", False)]
