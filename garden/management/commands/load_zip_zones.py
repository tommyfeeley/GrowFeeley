#Load zip-to-zone mappings from a CSV file.

#First generate the CSV by running: python build_zones.py
#(this uses the frostline zipcodes.csv to approximate zones from lat/lng)

#Then load it with: python manage.py load_zip_zones zip_zones.csv

#The CSV format should have columns: zipcode, zone
#Example row: 07921,6b

import csv
from django.core.management.base import BaseCommand
from garden.models import ZipToZone


class Command(BaseCommand):
    help = 'Load zip-to-zone data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to zip_zones.csv')

    def handle(self, *args, **options):
        csv_path = options['csv_file']

        self.stdout.write(f'Loading zip codes from {csv_path}...')

        entries = []
        seen = set()

        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)  # skip header row

            for row in reader:
                if len(row) < 2:
                    continue

                zip_code = row[0].strip()
                zone = row[1].strip().lower()

                if not zip_code or not zone or len(zip_code) != 5:
                    continue
                if zip_code in seen:
                    continue

                seen.add(zip_code)
                entries.append(ZipToZone(zip_code=zip_code, zone=zone))

        self.stdout.write(f'  Parsed {len(entries)} zip codes')

        if entries:
            ZipToZone.objects.all().delete()
            batch_size = 1000
            for i in range(0, len(entries), batch_size):
                ZipToZone.objects.bulk_create(entries[i:i + batch_size])

        self.stdout.write(self.style.SUCCESS(
            f'  Loaded {len(entries)} zip-to-zone mappings successfully!'
        ))
