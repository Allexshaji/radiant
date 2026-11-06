"""Turn a check-in location (latitude, longitude) into a short place name.

The name comes from OpenStreetMap's free lookup service (Nominatim). It asks every
client to identify itself and allows about one request a second, so each check-in
makes at most one request. If the lookup fails or is slow, the check-in still goes
through. The history then shows the coordinates instead of a name.
"""
import json
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "RadiantAyurvedaHR/1.0"
TIMEOUT_SECONDS = 3
# Keep the first few parts of the address, e.g. "Lulu Mall, Edappally, Ernakulam, Kerala".
ADDRESS_PARTS = 4
MAX_LENGTH = 255


def place_name_for(latitude, longitude):
    """A short place name for these coordinates, or "" when none can be found."""
    if latitude is None or longitude is None:
        return ""

    query = urlencode({
        "format": "jsonv2",
        "lat": latitude,
        "lon": longitude,
        "zoom": 16,
        "accept-language": "en",
    })
    request = Request(f"{NOMINATIM_URL}?{query}", headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        # Deliberately no details here: the message would contain the staff member's location.
        logger.warning("Place name lookup failed; the check-in was saved without a name.")
        return ""

    full_name = data.get("display_name", "") if isinstance(data, dict) else ""
    parts = [part.strip() for part in full_name.split(",") if part.strip()]
    return ", ".join(parts[:ADDRESS_PARTS])[:MAX_LENGTH]
