from django.shortcuts import render
import time
from .models import FishSpecies
from .services.preprocessing import AquariumEngine
from .services.csp import AquariumCSP
from .services.rules.engine import RuleEngine
from django.http import JsonResponse

from django.conf import settings
import os

RULES_PATH = os.path.join(
    settings.BASE_DIR,
    "core",
    "services",
    "rules",
    "rules.json"
)

def home_view(request):
    fish_list = FishSpecies.objects.all().order_by('name')
    # Pobieranie danych z formularza
    volume = request.GET.get('volume')
    temp = request.GET.get('temp')
    ph = request.GET.get('ph')
    strict_biotope = request.GET.get('strict_biotope') == 'on'
    base_fish_id = request.GET.get('base_fish')
    base_fish = None

    if base_fish_id:
        try:
            base_fish = FishSpecies.objects.get(id=base_fish_id)
        except FishSpecies.DoesNotExist:
            base_fish = None
    
    ranking = []
    total_process_time = 0
    solutions = []

    if volume:
        try:
            # 1. Konwersja i Preprocessing
            vol_int = int(volume)
            temp_float = float(temp) if temp else None
            ph_float = float(ph) if ph else None

            start_full_process = time.perf_counter()

            engine = AquariumEngine(
                volume=vol_int,
                temp=temp_float,
                ph=ph_float,
                base_fish=base_fish
            )

            candidates, pre_time = engine.get_filtered_candidates(use_preprocessing=True)
            
            if not candidates:
                return render(request, 'core/home.html', {
                    'ranking': [],
                    'error': 'Brak ryb spełniających wymagania.'
                })

            # 2. Biotop
            if strict_biotope:
                available_regions = set(
                    f.origin_region for f in candidates if f.origin_region
                )
                
                for region in available_regions:
                    region_candidates = [
                        f for f in candidates if f.origin_region == region
                    ]
                    csp = AquariumCSP(region_candidates, vol_int, base_fish=base_fish)
                    sols, _ = csp.solve()
                    solutions.extend(sols)
            else:
                csp = AquariumCSP(candidates, vol_int, base_fish=base_fish)
                solutions, _ = csp.solve()

            weights = {
                'zone_completeness': 30,
                'biomass_optimization': 25,
                'region_consistency': 20,
                'aggression_safety': 25
            }

            # 4. Ranking
            if solutions:
                ranker = RuleEngine(
                    solutions=solutions,
                    volume=vol_int,
                    base_fish_id=base_fish.id if base_fish else None,
                    rules_path=RULES_PATH
                )
                ranking = ranker.score_and_rank()
            
            total_process_time = time.perf_counter() - start_full_process

        except (ValueError, TypeError):
            return render(request, 'core/home.html', {
                'error': 'Wprowadź poprawne dane liczbowe.'
            })

    return render(request, 'core/home.html', {
        'ranking': ranking,
        'process_time': round(total_process_time, 4),
        'count': len(ranking),
        'query_params': request.GET,
        'fish_list': fish_list
    })

def fish_params(request, fish_id):
    try:
        fish = FishSpecies.objects.get(id=fish_id)
        return JsonResponse({
            'temp_min': fish.temp_min,
            'temp_max': fish.temp_max,
            'ph_min': fish.ph_min,
            'ph_max': fish.ph_max,
            'volume': fish.min_tank_volume,
        })
    except FishSpecies.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)