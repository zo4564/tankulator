from django.shortcuts import render
from .models import FishSpecies
from .services.recommender import AquariumEngine, AquariumCSP, RuleEngine

def home_view(request):
    volume = request.GET.get('volume')
    temp = request.GET.get('temp')
    ph = request.GET.get('ph')
    profile = request.GET.get('profile', 'zrównoważony')
    
    ranking = []
    process_time = 0

    if volume:
        # Konwersja danych
        vol_int = int(volume)
        temp_float = float(temp) if temp else 25.0
        ph_float = float(ph) if ph else 7.0

        # 1. Preprocessing
        engine = AquariumEngine(volume=vol_int, temp=temp_float, ph=ph_float)
        candidates, pre_time = engine.get_filtered_candidates(use_preprocessing=True)
        
        # 2. CSP (Twarde więzy)
        csp = AquariumCSP(candidates, vol_int, slot_count=3)
        solutions, csp_time = csp.solve()
        
        # 3. Definicja wag na podstawie PROFILU z formularza
        weights = {
            'zone_completeness': 15,
            'biodiversity_bonus': 10,
            'aggression_penalty': 8,
            'volume_efficiency': 5
        }

        if profile == 'bezpieczny':
            weights['aggression_penalty'] = 40  # Bardzo mocna kara za agresję
            weights['biodiversity_bonus'] = 20   # Premiuj mixy łagodne
        elif profile == 'esteta':
            weights['zone_completeness'] = 50    # Najważniejsze, żeby pływały wszędzie
            weights['volume_efficiency'] = 10

        strict_biotope = request.GET.get('strict_biotope')

        if strict_biotope:
            # 1. Sprawdzamy jakie regiony są dostępne po filtrze pH/Temp
            available_regions = candidates.values_list('origin_region', flat=True).distinct()
            
            # 2. Dla każdego regionu uruchamiamy CSP i łączymy wyniki
            all_solutions = []
            for region in available_regions:
                region_candidates = candidates.filter(origin_region=region)
                csp = AquariumCSP(region_candidates, vol_int)
                sols, _ = csp.solve()
                all_solutions.extend(sols)
            solutions = all_solutions

        # 4. Ranking (Miękkie więzy)
        rules = RuleEngine(solutions, weights=weights)
        ranking = rules.score_and_rank()
        
        process_time = pre_time + csp_time

    return render(request, 'core/home.html', {
        'ranking': ranking,
        'process_time': process_time,
        'count': len(ranking)
    })