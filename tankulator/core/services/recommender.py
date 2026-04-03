import time
from constraint import Problem
from ..models import FishSpecies

# --- PREPROCESSING ---
class AquariumEngine:
    def __init__(self, volume, temp=None, ph=None, hardness=None):
        self.volume = volume
        self.temp = temp
        self.ph = ph
        self.hardness = hardness

    def get_filtered_candidates(self, use_preprocessing=True):
        start_time = time.perf_counter()
        all_fish = FishSpecies.objects.all()
        
        if use_preprocessing:
            candidates = all_fish.filter(min_tank_volume__lte=self.volume)
            if self.temp:
                candidates = candidates.filter(temp_min__lte=self.temp, temp_max__gte=self.temp)
            if self.ph:
                candidates = candidates.filter(ph_min__lte=self.ph, ph_max__gte=self.ph)
            if self.hardness:
                candidates = candidates.filter(hardness_min__lte=self.hardness, hardness_max__gte=self.hardness)
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

        # 2. Parametry wody (Temp, pH i Twardość)
        def water_compatibility_constraint(*args):
            max_temp_min = max(f.temp_min for f in args)
            min_temp_max = min(f.temp_max for f in args)
            max_ph_min = max(f.ph_min for f in args)
            min_ph_max = min(f.ph_max for f in args)
            max_hard_min = max(f.hardness_min for f in args)
            min_hard_max = min(f.hardness_max for f in args)
            
            return (max_temp_min <= min_temp_max) and \
                   (max_ph_min <= min_ph_max) and \
                   (max_hard_min <= min_hard_max)

        self.problem.addConstraint(water_compatibility_constraint, self.slots)

        # 3. Twarde ograniczenie agresji
        def aggression_constraint(*args):
            for i in range(len(args)):
                for j in range(i + 1, len(args)):
                    if (args[i].aggression_level == 3 and args[j].aggression_level == 1) or \
                       (args[j].aggression_level == 3 and args[i].aggression_level == 1):
                        return False
            return True
        self.problem.addConstraint(aggression_constraint, self.slots)

        # 4. Ograniczenie stref (Zone) dla małych akwariów
        def zone_crowding_constraint(*args):
            if self.volume < 100:
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
        self.weights = weights or {
            'zone_completeness': 15,
            'biodiversity_bonus': 10,
            'aggression_penalty': 8,
            'volume_efficiency': 5
        }

    def score_and_rank(self):
        ranked_results = []

        for sol in self.solutions:
            fish_list = list(sol.values())
            score = 0
            
            occupied_zones = set(f.zone for f in fish_list)
            score += len(occupied_zones) * self.weights.get('zone_completeness', 15)
            
            if 'BTM' in occupied_zones:
                score += 20
            else:
                score -= 30
            
            has_schooling = any(f.is_schooling for f in fish_list)
            has_solo = any(not f.is_schooling for f in fish_list)
            if has_schooling and has_solo:
                score += self.weights['biodiversity_bonus']

            total_aggression = sum(f.aggression_level for f in fish_list)
            score -= total_aggression * self.weights['aggression_penalty']

            current_load = sum(f.bioload_index * (6 if f.is_schooling else 1) for f in fish_list)
            capacity_usage = current_load / (60 / 10) 

            regions = [f.origin_region for f in fish_list]
            unique_regions = set(regions)

            if len(unique_regions) == 1:
                score += 50 
            elif len(unique_regions) == 2:
                score += 15
            
            if 0.7 <= capacity_usage <= 0.9:
                score += self.weights['volume_efficiency'] * 2
            elif capacity_usage > 0.9:
                score -= self.weights['volume_efficiency'] * 3

            ranked_results.append({
                'fish_details': [
                    {'name': f.name, 'zone': f.zone, 'is_schooling': f.is_schooling} 
                    for f in fish_list
                ],
                'total_score': round(score, 2),
                'zones_summary': list(occupied_zones)
            })

        return sorted(ranked_results, key=lambda x: x['total_score'], reverse=True)