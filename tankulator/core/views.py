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
    hardness = request.GET.get('hardness')
    strict_biotope = request.GET.get('strict_biotope') == 'on'
    profile = request.GET.get("profile", "community")
    base_fish_id = request.GET.get('base_fish')
    base_fish = None

    if base_fish_id:
        try:
            base_fish = FishSpecies.objects.get(id=base_fish_id)
        except FishSpecies.DoesNotExist:
            base_fish = None
    
    ranking = []
    ranking_groups = []
    total_process_time = 0
    solutions = []

    if volume:
        try:
            # 1. Konwersja i Preprocessing
            vol_int = int(volume)
            temp_float = float(temp) if temp else None
            ph_float = float(ph) if ph else None
            hardness_float = float(hardness) if hardness else None

            start_full_process = time.perf_counter()

            engine = AquariumEngine(
                volume=vol_int,
                temp=temp_float,
                ph=ph_float,
                hardness=hardness_float,
                base_fish=base_fish
            )

            candidates, pre_time = engine.get_filtered_candidates(use_preprocessing=True)
            
            print("KANDYDACI:", len(candidates))

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

            # 4. Ranking
            if solutions:
                ranker = RuleEngine(
                    solutions=solutions,
                    volume=vol_int,
                    base_fish_id=base_fish.id if base_fish else None,
                    rules_path=RULES_PATH,
                    profile=profile
                )
                ranking = ranker.score_and_rank()

                from collections import defaultdict

                grouped_ranking = defaultdict(list)

                for result in ranking:

                    species_signature = tuple(
                        sorted(
                            fish["name"]
                            for fish in result["fish_details"]
                        )
                    )

                    grouped_ranking[species_signature].append(result)

                ranking_groups = []

                for signature, variants in grouped_ranking.items():

                    variants.sort(
                        key=lambda x: x["total_score"],
                        reverse=True
                    )

                    ranking_groups.append({
                        "signature": signature,
                        "best_score": variants[0]["total_score"],
                        "variants": variants,
                    })

                ranking_groups.sort(
                    key=lambda x: x["best_score"],
                    reverse=True
                )
            
            total_process_time = time.perf_counter() - start_full_process

            from .services.experiment_logger import log_exp

            log_exp(
                f"TOTAL_RUN;"
                f"VOLUME={vol_int};"
                f"CANDIDATES={len(candidates)};"
                f"SOLUTIONS={len(solutions)};"
                f"RANKED={len(ranking)};"
                f"TIME={total_process_time:.6f}"
            )

        except (ValueError, TypeError):
            return render(request, 'core/home.html', {
                'error': 'Wprowadź poprawne dane liczbowe.'
            })

    return render(request, 'core/home.html', {
        'ranking_groups': ranking_groups,
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
            'hardness_min': fish.hardness_min,
            'hardness_max': fish.hardness_max,
            'volume': fish.min_tank_volume,
        })
    except FishSpecies.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)