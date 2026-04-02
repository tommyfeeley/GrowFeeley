from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from .models import FrostDateByZone, Plant, CompanionRelationship
from .services import lookup_zone


def _get_zone_context(zip_code):
    # Helper: resolve a zip code to zone + frost data. Returns (frost_data, zone_str, error)
    if not zip_code:
        return None, None, None
    return lookup_zone(zip_code)


def home(request):
    #Landing page that prompts you for zipcode
    zip_code = request.GET.get('zip', '').strip()
    frost_data, zone_str, zone_error = _get_zone_context(zip_code)

    return render(request, 'garden/home.html', {
        'frost_data': frost_data,
        'zone_str': zone_str,
        'zone_error': zone_error,
        'zip_code': zip_code,
    })


def plant_list(request):
    #Browse/Search all plants
    plants = Plant.objects.all()
    query = request.GET.get('q', '')
    plant_type = request.GET.get('type', '')
    zip_code = request.GET.get('zip', '').strip()

    if query:
        plants = plants.filter(
            Q(name__icontains=query) | Q(variety__icontains=query)
        )
    if plant_type:
        plants = plants.filter(plant_type=plant_type)

    frost_data, zone_str, zone_error = _get_zone_context(zip_code)

    return render(request, 'garden/plant_list.html', {
        'plants': plants,
        'query': query,
        'plant_type': plant_type,
        'frost_data': frost_data,
        'zone_str': zone_str,
        'zip_code': zip_code,
        'plant_types': Plant.PlantType.choices,
    })


def plant_detail(request, pk):
    # Plant detail with personalized calendar
    plant = get_object_or_404(Plant, pk=pk)
    zip_code = request.GET.get('zip', '').strip()
    frost_data, zone_str, zone_error = _get_zone_context(zip_code)
    calendar = None

    if frost_data:
        calendar = plant.get_calendar(frost_data)

    # Get companion relationships
    companions = CompanionRelationship.objects.filter(
        Q(plant_a=plant) | Q(plant_b=plant)
    ).select_related('plant_a', 'plant_b')

    companion_data = []
    for rel in companions:
        other_plant = rel.plant_b if rel.plant_a == plant else rel.plant_a
        companion_data.append({
            'plant': other_plant,
            'relationship': rel.relationship,
            'reason': rel.reason,
        })

    return render(request, 'garden/plant_detail.html', {
        'plant': plant,
        'frost_data': frost_data,
        'zone_str': zone_str,
        'calendar': calendar,
        'zip_code': zip_code,
        'companions': companion_data,
    })


def my_garden(request):
    # Selected plants calendar view
    zip_code = request.GET.get('zip', '').strip()
    plant_ids = request.GET.getlist('plants')

    frost_data, zone_str, zone_error = _get_zone_context(zip_code)
    garden_data = []

    if frost_data and plant_ids:
        plants = Plant.objects.filter(pk__in=plant_ids)
        for plant in plants:
            garden_data.append({
                'plant': plant,
                'calendar': plant.get_calendar(frost_data),
            })

    # Get companion warnings for selected plants
    companion_warnings = []
    if plant_ids:
        selected_plants = Plant.objects.filter(pk__in=plant_ids)
        for rel in CompanionRelationship.objects.filter(
            plant_a__in=selected_plants, plant_b__in=selected_plants
        ).select_related('plant_a', 'plant_b'):
            companion_warnings.append(rel)

    return render(request, 'garden/my_garden.html', {
        'frost_data': frost_data,
        'zone_str': zone_str,
        'zip_code': zip_code,
        'garden_data': garden_data,
        'companion_warnings': companion_warnings,
        'all_plants': Plant.objects.all(),
    })


# --- API endpoints ---

def api_lookup_zone(request):
    #AJAX endpoint - search by zipcode
    zip_code = request.GET.get('zip', '').strip()
    frost_data, zone_str, error = lookup_zone(zip_code)

    if frost_data:
        return JsonResponse({
            'found': True,
            'zone': zone_str,
            'last_frost': frost_data.last_frost_for_year().strftime('%B %d'),
            'first_frost': frost_data.first_frost_for_year().strftime('%B %d'),
            'growing_season_days': frost_data.growing_season_days,
        })
    elif zone_str:
        return JsonResponse({
            'found': True,
            'zone': zone_str,
            'last_frost': None,
            'first_frost': None,
            'growing_season_days': None,
            'warning': error,
        })
    return JsonResponse({'found': False, 'error': error or 'Zip code not found.'})


def api_plant_search(request):
    #Ajax endpoint - search plants by name
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})

    plants = Plant.objects.filter(
        Q(name__icontains=query) | Q(variety__icontains=query)
    )[:10]

    results = [{'id': p.pk, 'name': p.display_name, 'type': p.plant_type} for p in plants]
    return JsonResponse({'results': results})
