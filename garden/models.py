from django.db import models
from datetime import timedelta, date


class FrostDateByZone(models.Model):
    #Average frost dates by USDA hardiness zone. ~15 rows covers the whole US.
    zone = models.CharField(max_length=5, unique=True, help_text="e.g. 4a, 6b, 7a")
    avg_last_frost = models.DateField(help_text="Average last spring frost (use 2000 as base year, e.g. 2000-04-15)")
    avg_first_frost = models.DateField(help_text="Average first fall frost (use 2000 as base year, e.g. 2000-10-15)")

    class Meta:
        ordering = ['zone']
        verbose_name = 'Frost Date by Zone'
        verbose_name_plural = 'Frost Dates by Zone'

    def __str__(self):
        return f"Zone {self.zone} — Last frost: {self.avg_last_frost.strftime('%b %d')}, First frost: {self.avg_first_frost.strftime('%b %d')}"

    @property
    def growing_season_days(self):
        return (self.avg_first_frost - self.avg_last_frost).days

    def last_frost_for_year(self, year=None):
        if year is None:
            year = date.today().year
        return self.avg_last_frost.replace(year=year)

    def first_frost_for_year(self, year=None):
        if year is None:
            year = date.today().year
        return self.avg_first_frost.replace(year=year)


class ZipToZone(models.Model):
    #Maps US zip codes to USDA hardiness zones. ~33,000 rows from frostline dataset.
    zip_code = models.CharField(max_length=5, unique=True, db_index=True)
    zone = models.CharField(max_length=5, help_text="e.g. 6b, 7a")

    class Meta:
        ordering = ['zip_code']
        verbose_name = 'Zip to Zone'
        verbose_name_plural = 'Zip to Zone Mappings'

    def __str__(self):
        return f"{self.zip_code} → Zone {self.zone}"


class Plant(models.Model):
    class PlantType(models.TextChoices):
        VEGETABLE = 'vegetable', 'Vegetable'
        FRUIT = 'fruit', 'Fruit'
        HERB = 'herb', 'Herb'
        FLOWER = 'flower', 'Flower'

    class SunRequirement(models.TextChoices):
        FULL_SUN = 'full_sun', 'Full Sun (6-8+ hrs)'
        PARTIAL_SUN = 'partial_sun', 'Partial Sun (4-6 hrs)'
        PARTIAL_SHADE = 'partial_shade', 'Partial Shade (2-4 hrs)'
        FULL_SHADE = 'full_shade', 'Full Shade (<2 hrs)'

    class WaterNeeds(models.TextChoices):
        LOW = 'low', 'Low'
        MODERATE = 'moderate', 'Moderate'
        HIGH = 'high', 'High'

    # Basic info
    name = models.CharField(max_length=100, help_text="Common name, e.g. 'Tomato'")
    variety = models.CharField(max_length=100, blank=True, help_text="Specific variety, e.g. 'Sun Sugar'")
    plant_type = models.CharField(max_length=20, choices=PlantType.choices)
    description = models.TextField(blank=True)

    # Growing requirements
    days_to_maturity_min = models.PositiveIntegerField(help_text="Minimum days from transplant/sow to harvest")
    days_to_maturity_max = models.PositiveIntegerField(help_text="Maximum days from transplant/sow to harvest")
    sun_requirement = models.CharField(max_length=20, choices=SunRequirement.choices)
    water_needs = models.CharField(max_length=20, choices=WaterNeeds.choices)
    spacing_inches = models.PositiveIntegerField(help_text="Space between plants in inches")
    seed_depth_inches = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    min_temp_f = models.IntegerField(help_text="Minimum temperature the plant can handle (°F)")

    # Timing relative to last frost
    start_indoors = models.BooleanField(default=False)
    weeks_start_indoors = models.IntegerField(
        null=True, blank=True,
        help_text="Weeks BEFORE last frost to start indoors (positive number)"
    )
    weeks_transplant = models.IntegerField(
        default=0,
        help_text="Weeks AFTER last frost to transplant outside"
    )
    can_direct_sow = models.BooleanField(default=True)
    weeks_direct_sow = models.IntegerField(
        null=True, blank=True,
        help_text="Weeks AFTER last frost for direct sow (negative = before)"
    )

    growing_tips = models.TextField(blank=True)

    class Meta:
        ordering = ['name', 'variety']
        unique_together = ['name', 'variety']

    def __str__(self):
        if self.variety:
            return f"{self.name} — {self.variety}"
        return self.name

    @property
    def display_name(self):
        if self.variety:
            return f"{self.name} ({self.variety})"
        return self.name

    def get_calendar(self, frost_data):
        #Calculate personalized planting dates for a given FrostDateByZone.
        year = date.today().year
        last_frost = frost_data.last_frost_for_year(year)
        first_frost = frost_data.first_frost_for_year(year)

        calendar = {
            'zone': frost_data.zone,
            'last_frost': last_frost,
            'first_frost': first_frost,
        }

        if self.start_indoors and self.weeks_start_indoors:
            calendar['start_indoors'] = last_frost - timedelta(weeks=self.weeks_start_indoors)

        if self.start_indoors:
            calendar['transplant'] = last_frost + timedelta(weeks=self.weeks_transplant)

        if self.can_direct_sow and self.weeks_direct_sow is not None:
            calendar['direct_sow'] = last_frost + timedelta(weeks=self.weeks_direct_sow)

        plant_date = calendar.get('transplant') or calendar.get('direct_sow')
        if plant_date:
            calendar['harvest_start'] = plant_date + timedelta(days=self.days_to_maturity_min)
            calendar['harvest_end'] = plant_date + timedelta(days=self.days_to_maturity_max)
            if self.min_temp_f > 32 and calendar['harvest_end'] > first_frost:
                calendar['frost_warning'] = True

        return calendar


class CompanionRelationship(models.Model):
    class RelationType(models.TextChoices):
        COMPANION = 'companion', 'Good Companion'
        ANTAGONIST = 'antagonist', 'Antagonist (Keep Apart)'

    plant_a = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name='companion_from')
    plant_b = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name='companion_to')
    relationship = models.CharField(max_length=20, choices=RelationType.choices)
    reason = models.TextField(help_text="Why these plants are companions or antagonists")

    class Meta:
        unique_together = ['plant_a', 'plant_b']
        ordering = ['plant_a__name', 'plant_b__name']

    def __str__(self):
        symbol = '✓' if self.relationship == 'companion' else '✗'
        return f"{symbol} {self.plant_a.name} ↔ {self.plant_b.name}"
