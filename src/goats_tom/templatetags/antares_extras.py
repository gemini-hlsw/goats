import json
from urllib.parse import quote

from django import template

register = template.Library()


@register.simple_tag
def antares_url(name: str | None, ra_hms: str | None, dec_dms: str | None) -> str:
    """
    Build an ANTARES LoCI URL.

    - If name contains 'ANT' → direct object page
    - Else → cone search (1 arcsec) using HMS/DMS strings
    """
    base = "https://antares.noirlab.edu/loci"

    if name and "ANT" in name:
        return f"{base}/{quote(name)}"

    if not ra_hms or not dec_dms:
        return base

    center = f"{ra_hms} {dec_dms}"

    payload = {
        "filters": [
            {
                "type": "sky_distance",
                "field": {
                    "distance": "0.0002777777777777778 degree",
                    "htm16": {"center": center},
                },
                "text": f'Cone Search: {center}, 1"',
            }
        ],
        "sortBy": "properties.newest_alert_observation_time",
        "sortDesc": True,
        "perPage": 25,
    }

    query = quote(json.dumps(payload, separators=(",", ":")))
    return f"{base}?query={query}"
