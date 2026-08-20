import json
from urllib.parse import quote

from django import template

from goats_tom.antares_client.config import ANTARESConfig

register = template.Library()


@register.simple_tag
def antares_url(
    names: list[str] | None, ra_hms: str | None, dec_dms: str | None
) -> str:
    """
    Build an ANTARES LoCI URL.

    - If any name is an ANTARES locus ID → direct object page
    - Else → cone search (1 arcsec) using HMS/DMS strings

    Parameters
    ----------
    names : list[str] | None
        Target name and aliases.
    ra_hms : str | None
        Right ascension in sexagesimal HMS.
    dec_dms : str | None
        Declination in sexagesimal DMS.

    Returns
    -------
    str
        The ANTARES URL.
    """
    base = f"{ANTARESConfig.get_url()}/loci"

    locus_id = next((n for n in names or [] if n and n.startswith("ANT")), None)
    if locus_id:
        return f"{base}/{quote(locus_id)}"

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
