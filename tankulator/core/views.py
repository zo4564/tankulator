from django.shortcuts import render
import time
from .models import FishSpecies
from .services.recommender import AquariumEngine, AquariumCSP, RuleEngine

def home_view(request):
    # Pobieranie danych z formularza
    volume = request.GET.get('volume')
    temp = request.GET.get('temp')
    ph = request.GET.get('ph')
    profile = request.GET.get('profile', 'zrównoważony')
    strict_biotope = request.GET.get('strict_biotope') == 'on' # Checkboxy w HTML przesyłają 'on'
    
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

            engine = AquariumEngine(volume=vol_int, temp=temp_float, ph=ph_float)
            # candidates to teraz lista obiektów po "agresywnym" filtrze
            candidates, pre_time = engine.get_filtered_candidates(use_preprocessing=True)
            
            if not candidates:
                return render(request, 'core/home.html', {'ranking': [], 'error': 'Brak ryb spełniających wymagania.'})

            # 2. Logika Biotopu (Grupowanie przed CSP)
            if strict_biotope:
                # Wyciągamy unikalne regiony z przefiltrowanych kandydatów
                available_regions = set(f.origin_region for f in candidates if f.origin_region)
                
                for region in available_regions:
                    region_candidates = [f for f in candidates if f.origin_region == region]
                    csp = AquariumCSP(region_candidates, vol_int)
                    sols, _ = csp.solve()
                    solutions.extend(sols)
            else:
                # Standardowe CSP dla wszystkich pasujących ryb
                csp = AquariumCSP(candidates, vol_int)
                solutions, _ = csp.solve()

            # 3. Definicja wag na podstawie profilu
            # Dopasowałem klucze do tych, które mamy w nowym RuleEngine
            weights = {
                'zone_completeness': 20,
                'biomass_optimization': 30,
                'region_consistency': 25,
                'aggression_safety': 15
            }

            if profile == 'bezpieczny':
                weights['aggression_safety'] = 50
                weights['biomass_optimization'] = 10 # Mniejsze parcie na max ryb
            elif profile == 'esteta':
                weights['zone_completeness'] = 60
                weights['region_consistency'] = 10

            # 4. Ranking i punktacja
            if solutions:
                ranker = RuleEngine(solutions=solutions, volume=vol_int, weights=weights)
                ranking = ranker.score_and_rank()
            
            total_process_time = time.perf_counter() - start_full_process

        except (ValueError, TypeError):
            return render(request, 'core/home.html', {'error': 'Wprowadź poprawne dane liczbowe.'})

    return render(request, 'core/home.html', {
        'ranking': ranking,
        'process_time': round(total_process_time, 4),
        'count': len(ranking),
        'query_params': request.GET
    })