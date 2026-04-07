
#Fetch real USDA zone data from phzmapi.org for all zip codes.
#Takes ~30-60 minutes but only needs to run once.
#Run locally: python build_zones.py

import csv
import json
import urllib.request
import time
import os

INPUT = 'zipcodes.csv'
OUTPUT = 'zip_zones.csv'

# Resume support — if we already have partial results, skip those
done = set()
if os.path.exists(OUTPUT):
    with open(OUTPUT, 'r') as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if row:
                done.add(row[0])
    print(f"Resuming — {len(done)} already fetched")

# Read all zip codes
zip_codes = []
with open(INPUT, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        zc = row.get('zipcode', '').strip()
        if len(zc) == 5 and zc not in done:
            zip_codes.append(zc)

print(f"{len(zip_codes)} zip codes to fetch")

# Open output file in append mode
write_header = not os.path.exists(OUTPUT) or len(done) == 0
with open(OUTPUT, 'a', newline='') as f:
    writer = csv.writer(f)
    if write_header:
        writer.writerow(['zipcode', 'zone'])

    errors = 0
    for i, zc in enumerate(zip_codes):
        if i % 100 == 0:
            print(f"  {i}/{len(zip_codes)} ({i + len(done)} total)...")

        url = f'https://phzmapi.org/{zc}.json'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'GrowFeeley/1.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                zone = data.get('zone', '').strip().lower()
                if zone:
                    writer.writerow([zc, zone])
                    f.flush()
        except Exception:
            errors += 1

        # Small delay to be polite
        time.sleep(0.05)

print(f"\nDone! Errors: {errors}")
print(f"Results in {OUTPUT}")