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

        # Zmienne: każdy slot to jeden gatunek
        self.problem.addVariables(self.slots, self.candidates)

        # Ograniczenie: Gatunki nie mogą się powtarzać
        def unique_species(*args):
            return len(set(f.id for f in args)) == len(args)
        self.problem.addConstraint(unique_species, self.slots)

        # Ograniczenie: Przecięcie zakresów parametrów wody
        def water_compatibility_constraint(*args):
            max_temp_min = max(f.temp_min for f in args)
            min_temp_max = min(f.temp_max for f in args)
            max_ph_min = max(f.ph_min for f in args)
            min_ph_max = min(f.ph_max for f in args)
            return (max_temp_min <= min_temp_max) and (max_ph_min <= min_ph_max)

        self.problem.addConstraint(water_compatibility_constraint, self.slots)

        # Ograniczenie: Bioload
        def bioload_constraint(*args):
            total_load = sum(f.bioload_index for f in args)
            return total_load <= (self.volume / 10)

        self.problem.addConstraint(bioload_constraint, self.slots)

        start_time = time.perf_counter()
        solutions = self.problem.getSolutions()
        end_time = time.perf_counter()
        
        return solutions, (end_time - start_time)

# --- MODUŁ REGUŁOWY ---    
class RuleEngine:
    def __init__(self, solutions, weights=None):
        self.solutions = solutions
        self.weights = weights or {
            'zone_diversity': 10,   # Bonus za ryby w różnych strefach
            'aggression_penalty': 5  # Kara za sumaryczną agresję
        }

    def score_and_rank(self):
        ranked_results = []

        for sol in self.solutions:
            fish_list = sol.values()
            score = 0
            
            # Reguła 1: Różnorodność stref (TOP, MID, BTM)
            unique_zones = len(set(f.zone for f in fish_list))
            score += unique_zones * self.weights['zone_diversity']
            
            # Reguła 2: Agresywność (im wyższa, tym gorzej dla ogólnego wyniku)
            total_aggression = sum(f.aggression_level for f in fish_list)
            score -= total_aggression * self.weights['aggression_penalty']
            
            ranked_results.append({
                'fish_names': [f.name for f in fish_list],
                'score': score
            })

        # Sortowanie od najwyższego wyniku
        return sorted(ranked_results, key=lambda x: x['score'], reverse=True)

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