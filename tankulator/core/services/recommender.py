import time
from constraint import Problem
from ..models import FishSpecies

# --- PREPROCESSING ---
class AquariumEngine:
    def __init__(self, volume, temp=None, ph=None):
        self.volume = volume
        self.temp = temp
        self.ph = ph

    def get_filtered_candidates(self, use_preprocessing=True):
        start_time = time.perf_counter()
        all_fish = FishSpecies.objects.all()
        
        if use_preprocessing:
            candidates = all_fish.filter(min_tank_volume__lte=self.volume)
            if self.temp:
                candidates = candidates.filter(temp_min__lte=self.temp, temp_max__gte=self.temp)
            if self.ph:
                candidates = candidates.filter(ph_min__lte=self.ph, ph_max__gte=self.ph)
        else:
            candidates = all_fish
            
        end_time = time.perf_counter()
        return candidates, (end_time - start_time)

# --- MODUŁ CSP ---
class AquariumCSP:
    def __init__(self, candidates, volume, slot_count=3):
        self.problem = Problem()
        self.candidates = list(candidates)
        self.volume = volume
        self.slots = [f"gatunek_{i}" for i in range(slot_count)]

    def solve(self):
        if not self.candidates:
            return [], 0

        self.problem.addVariables(self.slots, self.candidates)

        # eliminacja symetrii
        def symmetry_breaking_constraint(*args):
            for i in range(len(args) - 1):
                if args[i].id >= args[i+1].id:
                    return False
            return True
        
        self.problem.addConstraint(symmetry_breaking_constraint, self.slots)
        
        # 1. Gatunki nie mogą się powtarzać
        def unique_species(*args):
            return len(set(f.id for f in args)) == len(args)
        self.problem.addConstraint(unique_species, self.slots)

        # 2. Parametry wody (Temp i pH)
        def water_compatibility_constraint(*args):
            max_temp_min = max(f.temp_min for f in args)
            min_temp_max = min(f.temp_max for f in args)
            max_ph_min = max(f.ph_min for f in args)
            min_ph_max = min(f.ph_max for f in args)
            return (max_temp_min <= min_temp_max) and (max_ph_min <= min_ph_max)
        self.problem.addConstraint(water_compatibility_constraint, self.slots)

        # 3. NOWOŚĆ: Twarde ograniczenie agresji
        def aggression_constraint(*args):
            for i in range(len(args)):
                for j in range(i + 1, len(args)):
                    # Jeśli jedna ryba jest agresywna (3), a druga łagodna (1) -> odrzuć
                    if (args[i].aggression_level == 3 and args[j].aggression_level == 1) or \
                       (args[j].aggression_level == 3 and args[i].aggression_level == 1):
                        return False
            return True
        self.problem.addConstraint(aggression_constraint, self.slots)

        # 4. NOWOŚĆ: Ograniczenie stref (Zone) dla małych akwariów
        def zone_crowding_constraint(*args):
            if self.volume < 100:
                # W małym akwarium max 1 gatunek w danej strefie (szczególnie dno)
                zones = [f.zone for f in args]
                if zones.count('BTM') > 1: return False
            return True
        self.problem.addConstraint(zone_crowding_constraint, self.slots)

        # 5. Bioload (z uwzględnieniem ławicowości)
        def bioload_constraint(*args):
            total_load = sum(f.bioload_index * (3 if f.is_schooling else 1) for f in args)
            return total_load <= (self.volume / 8) 
        
        self.problem.addConstraint(bioload_constraint, self.slots)

        def size_conflict_constraint(*args):
            sizes = [f.adult_size for f in args]
            max_s = max(sizes)
            min_s = min(sizes)
            
            # Reguła: Jeśli największa ryba jest >= 10cm, 
            # a najmniejsza < 4cm -> konflikt (ryzyko zjedzenia)
            if max_s >= 10.0 and min_s < 4.0:
                return False
            return True

        self.problem.addConstraint(size_conflict_constraint, self.slots)

        start_time = time.perf_counter()
        solutions = self.problem.getSolutions()
        end_time = time.perf_counter()
        
        return solutions, (end_time - start_time)

# --- MODUŁ REGUŁOWY ---    

class RuleEngine:
    def __init__(self, solutions, weights=None):
        self.solutions = solutions
        # Wagi pozwalają na łatwe sterowanie "osobowością" algorytmu
        self.weights = weights or {
            'zone_completeness': 15,  # Bonus za obsadzenie każdej strefy (TOP, MID, BTM)
            'biodiversity_bonus': 10, # Bonus za różne typy ryb (ławicowe vs soliści)
            'aggression_penalty': 8,  # Kara za sumaryczny poziom stresu w zbiorniku
            'volume_efficiency': 5    # Bonus za optymalne wykorzystanie litrażu (nie za puste, nie za pełne)
        }

    def score_and_rank(self):
        ranked_results = []

        for sol in self.solutions:
            # W python-constraint sol to słownik { 'gatunek_0': FishObject, ... }
            fish_list = list(sol.values())
            score = 0
            
            # --- REGUŁA 1: KOMPLETNOŚĆ STREF (Estetyka) ---
            occupied_zones = set(f.zone for f in fish_list)
            
            # Bonus bazowy za każdą strefę
            score += len(occupied_zones) * self.weights.get('zone_completeness', 15)
            
            # SPECJALNY BONUS ZA DNO: 
            # W akwarystyce dno (BTM) jest kluczowe dla czystości (zjadanie resztek)
            if 'BTM' in occupied_zones:
                score += 20  # Dodatkowe 20 pkt za posiadanie ekipy sprzątającej dno
            else:
                score -= 30  # Kara za brak ryb dennych
            
            # --- REGUŁA 2: MIX BEHAWIORALNY ---
            # Premiujemy zestawienie, gdzie jest przynajmniej jedna ławica i jeden "charakterystyczny" solista
            has_schooling = any(f.is_schooling for f in fish_list)
            has_solo = any(not f.is_schooling for f in fish_list)
            if has_schooling and has_solo:
                score += self.weights['biodiversity_bonus']

            # --- REGUŁA 3: SUMARYCZNA AGRESJA (Komfort) ---
            # Nawet jeśli ryby się nie pozabijają (CSP), to dużo terytorialnych ryb (Level 2)
            # obniża ocenę estetyczną (ciągłe gonitwy)
            total_aggression = sum(f.aggression_level for f in fish_list)
            score -= total_aggression * self.weights['aggression_penalty']

            # --- REGUŁA 4: EFEKTYWNOŚĆ WYKORZYSTANIA PRZESTRZENI ---
            # Obliczamy jak blisko limitu bioloadu jesteśmy (zakładając 1.0 na 10L)
            current_load = sum(f.bioload_index * (6 if f.is_schooling else 1) for f in fish_list)
            capacity_usage = current_load / (60 / 10) # Przykładowy limit dla 60L

            #reguła biotopów
            regions = [f.origin_region for f in fish_list]
            unique_regions = set(regions)

            if len(unique_regions) == 1:
                # Bonus za "Pure Biotope"
                score += 50 
            elif len(unique_regions) == 2:
                # Bonus za częściową zgodność
                score += 15
            
            # Najlepsze punkty za wykorzystanie 70-90% pojemności (nie za puste, nie przerybione)
            if 0.7 <= capacity_usage <= 0.9:
                score += self.weights['volume_efficiency'] * 2
            elif capacity_usage > 0.9:
                score -= self.weights['volume_efficiency'] * 3 # Karny punkt za "ściski"

            ranked_results.append({
                'fish_details': [
                    {'name': f.name, 'zone': f.zone, 'is_schooling': f.is_schooling} 
                    for f in fish_list
                ],
                'total_score': round(score, 2),
                'zones_summary': list(occupied_zones)
            })

        # Sortowanie od najwyższego wyniku
        return sorted(ranked_results, key=lambda x: x['total_score'], reverse=True)

# --- FUNKCJE TESTOWE ---
def test_ranking(volume, weights=None):
    # 1. Preprocessing
    engine = AquariumEngine(volume=volume)
    candidates, _ = engine.get_filtered_candidates()
    
    # 2. CSP
    csp = AquariumCSP(candidates, volume, slot_count=3)
    solutions, _ = csp.solve()
    
    # 3. System Regułowy (Scoring)
    rules = RuleEngine(solutions, weights)
    ranking = rules.score_and_rank()
    
    print(f"--- RANKING DLA {volume}L ---")
    for i, res in enumerate(ranking[:3]): # Pokazujemy top 3
        print(f"{i+1}. {res['fish_names']} - Wynik: {res['score']}")
    
    return ranking

def test_full_logic(volume, use_pre=True):
    # Wywołujemy Preprocessing
    engine = AquariumEngine(volume=volume)
    candidates, pre_time = engine.get_filtered_candidates(use_preprocessing=use_pre)
    
    # Wywołujemy CSP
    csp = AquariumCSP(candidates, volume, slot_count=2)
    solutions, csp_time = csp.solve()
    
    print(f"Wynik dla {volume}L (Pre: {use_pre}):")
    print(f" - Kandydatów: {len(candidates)}")
    print(f" - Czas Preprocessingu: {pre_time:.6f}s")
    print(f" - Czas CSP: {csp_time:.6f}s")
    print(f" - Liczba rozwiązań: {len(solutions)}")
    
    return solutions

def test_preprocessing(volume):
    engine = AquariumEngine(volume=volume)
    candidates, duration = engine.get_filtered_candidates(use_preprocessing=True)
    print(f"Znaleziono {candidates.count()} gatunków dla akwarium {volume}L.")
    print(f"Czas preprocessingu: {duration:.6f} sekund.")
    return candidates