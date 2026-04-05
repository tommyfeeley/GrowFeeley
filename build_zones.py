"""
Build a zip-to-zone CSV from the frostline zipcodes.csv.
Uses latitude + state to approximate USDA hardiness zones.

This is a reasonable approximation — the USDA zones are primarily driven by
latitude and distance from the coast, with adjustments for altitude and
regional climate patterns.

Run locally: python build_zones.py
Reads: zipcodes.csv (from frostline - has zipcode, city, state, latitude, longitude)
Writes: zip_zones.csv (zipcode, zone)
"""
import csv


def lat_lng_to_zone(lat, lng, state):
    """
    Approximate USDA hardiness zone from latitude, longitude, and state.
    This is a simplified model but covers the continental US reasonably well.
    """
    lat = float(lat)
    lng = float(lng)

    # Hawaii - mostly 11-13
    if state == 'HI':
        if lat > 20.5:
            return '11a'
        return '12a'

    # Puerto Rico / US Virgin Islands
    if state in ('PR', 'VI', 'GU', 'AS'):
        return '13a'

    # Alaska
    if state == 'AK':
        if lat > 64:
            return '2a'
        elif lat > 62:
            return '3a'
        elif lat > 60:
            return '4a'
        elif lat > 58:
            return '5a'
        else:
            return '6a'

    # Continental US - base zone from latitude
    # General pattern: higher latitude = lower zone
    if lat >= 48:
        base = 3
    elif lat >= 46:
        base = 4
    elif lat >= 44:
        base = 4.5
    elif lat >= 42:
        base = 5
    elif lat >= 40.5:
        base = 5.5
    elif lat >= 39:
        base = 6
    elif lat >= 37.5:
        base = 6.5
    elif lat >= 36:
        base = 7
    elif lat >= 34:
        base = 7.5
    elif lat >= 32:
        base = 8
    elif lat >= 30:
        base = 8.5
    elif lat >= 28:
        base = 9
    elif lat >= 26:
        base = 9.5
    elif lat >= 24:
        base = 10
    else:
        base = 10.5

    # Coastal warming effect (east coast south of Virginia, Gulf, and Pacific coast)
    # West coast is generally warmer for the latitude
    if lng > -82 and lat < 35:
        # Southeast coast / Florida
        base += 0.5
    if lng > -90 and lng < -80 and lat < 32:
        # Gulf coast
        base += 0.5
    if lng < -117 and lat < 40 and lat > 32:
        # Southern California coast
        base += 1
    elif lng < -120 and lat >= 40 and lat < 49:
        # Pacific Northwest coast - milder
        base += 0.5

    # Mountain/elevation effect (approximate — Rocky Mountain states are colder)
    mountain_states = {'MT', 'WY', 'CO', 'ID', 'UT', 'NM'}
    if state in mountain_states:
        base -= 1
    # Northern plains are colder
    if state in ('ND', 'SD', 'MN'):
        base -= 0.5
    # Upper midwest
    if state in ('WI', 'MI') and lat > 44:
        base -= 0.5

    # Clamp to valid range
    base = max(1, min(13, base))

    # Convert to zone string (e.g., 6.5 -> "6b", 7 -> "7a")
    zone_num = int(base)
    zone_sub = 'b' if (base % 1) >= 0.5 else 'a'

    return f"{zone_num}{zone_sub}"


def main():
    input_file = 'zipcodes.csv'
    output_file = 'zip_zones.csv'

    results = []
    skipped = 0

    with open(input_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            zipcode = row.get('zipcode', '').strip()
            lat = row.get('latitude', '').strip()
            lng = row.get('longitude', '').strip()
            state = row.get('state', '').strip()

            if not zipcode or not lat or not lng or len(zipcode) != 5:
                skipped += 1
                continue

            try:
                zone = lat_lng_to_zone(lat, lng, state)
                results.append((zipcode, zone))
            except (ValueError, TypeError):
                skipped += 1

    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['zipcode', 'zone'])
        for zc, zone in results:
            writer.writerow([zc, zone])

    print(f"Processed {len(results)} zip codes, skipped {skipped}")
    print(f"Saved to {output_file}")

    # Print zone distribution
    from collections import Counter
    zone_counts = Counter(zone for _, zone in results)
    print("\nZone distribution:")
    for zone in sorted(zone_counts.keys()):
        print(f"  {zone}: {zone_counts[zone]}")


if __name__ == '__main__':
    main()
