
#Zone lookup service.
#Resolves a zip code to a USDA hardiness zone via local ZipToZone table,
#then looks up frost dates from FrostDateByZone.
import logging

from .models import FrostDateByZone, ZipToZone

logger = logging.getLogger(__name__)


def lookup_zone(zip_code):
    #Look up zone + frost data for a zip code using local database.

    #Returns: (frost_data: FrostDateByZone | None, zone_str: str | None, error: str | None)
    if not zip_code or len(zip_code) != 5 or not zip_code.isdigit():
        return None, None, 'Invalid zip code.'

    # Look up zip → zone from local table
    zip_entry = ZipToZone.objects.filter(zip_code=zip_code).first()
    if not zip_entry:
        return None, None, 'Zip code not found. Make sure it is a valid US zip code.'

    zone_str = zip_entry.zone.lower()

    # Look up frost dates for this zone
    frost_data = _get_frost_data(zone_str)
    if not frost_data:
        return None, zone_str, f'Found zone {zone_str} but no frost date data for this zone.'

    return frost_data, zone_str, None


def _get_frost_data(zone_str):
    #Look up FrostDateByZone for a zone string.
    #Tries exact match first, then falls back to the base zone.
    frost_data = FrostDateByZone.objects.filter(zone=zone_str).first()
    if frost_data:
        return frost_data

    # Fallback: if we have '6b' but only '6a' in DB (or vice versa)
    if len(zone_str) >= 2:
        base_zone = zone_str[:-1]
        frost_data = FrostDateByZone.objects.filter(zone__startswith=base_zone).first()
        if frost_data:
            return frost_data

    return None
