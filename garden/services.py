"""
Zone lookup service.
Resolves a zip code to a USDA hardiness zone via phzmapi.org,
then looks up frost dates from our FrostDateByZone table.
"""
import urllib.request
import json
import logging

from .models import FrostDateByZone

logger = logging.getLogger(__name__)

# Cache zone lookups in memory so we don't re-hit the API for the same zip in one session.
# In production you might want Django's cache framework instead.
_zone_cache = {}


def lookup_zone(zip_code):
    # Look up zone + frost data for a zip code.
    # Returns a FrostDateByZone object if found, or None.
    # Also returns the zone string separately (in case we have zone but no frost data)
    # Returns: (frost_data: FrostDateByZone | None, zone_str: str | None, error: str | None)

    if not zip_code or len(zip_code) != 5 or not zip_code.isdigit():
        return None, None, 'Invalid zip code.'

    # Check memory cache first
    if zip_code in _zone_cache:
        zone_str = _zone_cache[zip_code]
        frost_data = _get_frost_data(zone_str)
        return frost_data, zone_str, None

    # Call phzmapi.org (open source api for almost all us zipcodes)
    zone_str = _fetch_zone_from_api(zip_code)
    if not zone_str:
        return None, None, 'Could not find hardiness zone for this zip code.'

    # Cache it
    _zone_cache[zip_code] = zone_str

    # Look up frost dates
    frost_data = _get_frost_data(zone_str)
    if not frost_data:
        return None, zone_str, f'Found zone {zone_str} but no frost date data for this zone yet.'

    return frost_data, zone_str, None


def _fetch_zone_from_api(zip_code):
    # Fetch hardiness zone from phzmapi.org. Returns zone string like '6b' or None.
    url = f'https://phzmapi.org/{zip_code}.json'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GardenApp/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            # Response format: {"zone": "6b", "coordinates": {...}, "temperature_range": "..."}
            zone = data.get('zone', '')
            if zone:
                return zone.lower()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.info(f'Zip code {zip_code} not found in phzmapi.org')
        else:
            logger.warning(f'phzmapi.org HTTP error for {zip_code}: {e.code}')
    except Exception as e:
        logger.warning(f'phzmapi.org request failed for {zip_code}: {e}')
    return None


def _get_frost_data(zone_str):
    # Look up FrostDateByZone for a zone string.
    # Tries exact match first (e.g. '6b'), then falls back to the base zone (e.g. '6a' or '6b').
    
    # Exact match
    frost_data = FrostDateByZone.objects.filter(zone=zone_str).first()
    if frost_data:
        return frost_data

    # Fallback: if we have '6b' but only '6a' in DB (or vice versa), use the closest
    if len(zone_str) >= 2:
        base_zone = zone_str[:-1]  # e.g. '6' from '6b'
        frost_data = FrostDateByZone.objects.filter(zone__startswith=base_zone).first()
        if frost_data:
            return frost_data

    return None
