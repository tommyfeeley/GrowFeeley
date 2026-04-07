from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse, path
from django.utils.html import format_html
from .models import FrostDateByZone, ZipToZone, Plant, CompanionRelationship


@admin.register(FrostDateByZone)
class FrostDateByZoneAdmin(admin.ModelAdmin):
    list_display = ('zone', 'avg_last_frost', 'avg_first_frost', 'growing_season_days')
    ordering = ('zone',)


@admin.register(ZipToZone)
class ZipToZoneAdmin(admin.ModelAdmin):
    list_display = ('zip_code', 'zone')
    search_fields = ('zip_code',)
    list_filter = ('zone',)


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ('name', 'variety', 'plant_type', 'days_to_maturity_min', 'days_to_maturity_max',
                    'sun_requirement', 'start_indoors', 'can_direct_sow', 'duplicate_link')
    list_filter = ('plant_type', 'sun_requirement', 'water_needs', 'start_indoors', 'can_direct_sow', 'name')
    search_fields = ('name', 'variety')
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'variety', 'plant_type', 'description')
        }),
        ('Growing Requirements', {
            'fields': ('days_to_maturity_min', 'days_to_maturity_max', 'sun_requirement',
                       'water_needs', 'spacing_inches', 'seed_depth_inches', 'min_temp_f')
        }),
        ('Planting Timing', {
            'fields': ('start_indoors', 'weeks_start_indoors', 'weeks_transplant',
                       'can_direct_sow', 'weeks_direct_sow'),
            'description': 'Timing is relative to last frost date.'
        }),
        ('Tips', {
            'fields': ('growing_tips',)
        }),
    )
    actions = ['duplicate_selected']

    def duplicate_link(self, obj):
        #Show a 'Duplicate' link in the list view for each plant.
        url = reverse('admin:garden_plant_duplicate', args=[obj.pk])
        return format_html('<a href="{}">Duplicate</a>', url)
    duplicate_link.short_description = 'Quick Add'

    def get_urls(self):
        #Add custom URL for the duplicate view.
        custom_urls = [
            path(
                '<int:pk>/duplicate/',
                self.admin_site.admin_view(self.duplicate_view),
                name='garden_plant_duplicate',
            ),
        ]
        return custom_urls + super().get_urls()

    def duplicate_view(self, request, pk):
    #Redirect to the 'add' page with all fields pre-filled from the source plant.
    #Clears the variety so you just type the new variety name.
        source = Plant.objects.get(pk=pk)

        # Build query params to prefill the add form
        params = {
            'name': source.name,
            'variety': '',  # Clear this so they type the new variety
            'plant_type': source.plant_type,
            'description': '',  # Clear — they'll write a new description
            'days_to_maturity_min': source.days_to_maturity_min,
            'days_to_maturity_max': source.days_to_maturity_max,
            'sun_requirement': source.sun_requirement,
            'water_needs': source.water_needs,
            'spacing_inches': source.spacing_inches,
            'min_temp_f': source.min_temp_f,
            'start_indoors': int(source.start_indoors),  # Django admin uses 0/1 for booleans in URL
            'weeks_transplant': source.weeks_transplant,
            'can_direct_sow': int(source.can_direct_sow),
        }
        # Optional fields
        if source.seed_depth_inches is not None:
            params['seed_depth_inches'] = source.seed_depth_inches
        if source.weeks_start_indoors is not None:
            params['weeks_start_indoors'] = source.weeks_start_indoors
        if source.weeks_direct_sow is not None:
            params['weeks_direct_sow'] = source.weeks_direct_sow

        query_string = '&'.join(f'{k}={v}' for k, v in params.items())
        add_url = reverse('admin:garden_plant_add')
        return HttpResponseRedirect(f'{add_url}?{query_string}')

    @admin.action(description='Duplicate selected plants')
    def duplicate_selected(self, request, queryset):
        """Bulk action: duplicate selected plants (sets variety to 'Copy')."""
        created = 0
        for plant in queryset:
            plant.pk = None  # This makes Django create a new object on save
            plant.variety = f'{plant.variety} (Copy)' if plant.variety else 'Copy'
            try:
                plant.save()
                created += 1
            except Exception:
                pass  # Skip if duplicate name+variety combo
        self.message_user(request, f'{created} plant(s) duplicated. Edit the copies to set the correct variety and details.')


@admin.register(CompanionRelationship)
class CompanionRelationshipAdmin(admin.ModelAdmin):
    list_display = ('plant_a', 'plant_b', 'relationship', 'reason')
    list_filter = ('relationship',)
    search_fields = ('plant_a__name', 'plant_b__name')
    autocomplete_fields = ('plant_a', 'plant_b')
