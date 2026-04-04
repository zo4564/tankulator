import time
import copy
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
        candidates = FishSpecies.objects.all()
        
        if use_preprocessing:
            # 1. Filtry bazowe (litraż i parametry)
            candidates = candidates.filter(min_tank_volume__lte=self.volume)

            if self.temp:
                candidates = candidates.filter(temp_min__lte=self.temp, temp_max__gte=self.temp)
            if self.ph:
                candidates = candidates.filter(ph_min__lte=self.ph, ph_max__gte=self.ph)
            if self.hardness:
                candidates = candidates.filter(hardness_min__lte=self.hardness, hardness_max__gte=self.hardness)

            # 2. Filtr fizyczny (wielkość ryby)
            estimated_max_length = (self.volume ** (1/3)) * 4 
            candidates = [f for f in candidates if f.adult_size <= estimated_max_length]

            # 3. Weryfikacja biomasy stada minimalnego
            final_candidates = []
            for f in candidates:
                min_qty = 6 if f.is_schooling else 1
                if (f.adult_size * min_qty) <= (self.volume / 2):
                    final_candidates.append(f)
            
            # 4. Agresywne cięcie dla wydajności (Top 25 najlepiej pasujących pod pH)
            if len(final_candidates) > 25:
                target_ph = self.ph if self.ph else 7.0
                final_candidates = sorted(
                    final_candidates, 
                    key=lambda f: abs(((f.ph_min + f.ph_max) / 2) - target_ph)
                )[:25]
            candidates = final_candidates

        end_time = time.perf_counter()
        return candidates, (end_time - start_time)

# --- MODUŁ CSP ---

class AquariumCSP:
    def __init__(self, candidates, volume):
        self.problem = Problem()
        self.candidates = list(candidates)
        self.volume = volume
        self.species_ids = [f.id for f in self.candidates]
        self.species_map = {f.id: f for f in self.candidates}
        self.iteration_count = 0 

    def solve(self):
        if not self.candidates:
            return [], 0

        print(f"\n--- START CSP ---")

        # --- DEFINICJA DOMEN (SKOKOWE) ---
        for fish in self.candidates:
            # Ile cm ryby przypada na 1 sztukę
            bioload_per_fish = fish.adult_size if fish.adult_size > 0 else 5
            max_possible = int((self.volume / 2) / bioload_per_fish)
            
            if fish.is_schooling:
                # Ryby ławicowe: 0 LUB stado (6, 10, 15, 20, 25...)
                # Skok co 5 sztuk drastycznie redukuje liczbę kombinacji
                domain = [0, 6] 
                domain += [i for i in range(10, min(max_possible, 20) + 1, 10)]
            else:
                # Ryby samotne/pary: 0, 1 lub 2
                domain = [0, 1]
                if max_possible >= 2:
                    domain.append(2)
            
            # Usuwamy duplikaty i sortujemy
            domain = sorted(list(set(domain)))
            self.problem.addVariable(fish.id, domain)
            print(f"Zoptymalizowana domena dla {fish.name}: {domain}")

        # --- OGRANICZENIA ---

        def diversity_constraint(*counts):
            self.iteration_count += 1
            if self.iteration_count % 5000 == 0:
                print(f"Przetworzono {self.iteration_count} kombinacji...")

            active_species = [c for c in counts if c > 0]
            # Max 3 gatunki to optymalny balans dla algorytmu i estetyki akwarium
            return 1 <= len(active_species) <= 3

        def water_compatibility_constraint(*counts):
            selected_fish = [self.species_map[self.species_ids[i]] 
                            for i, count in enumerate(counts) if count > 0]
            if not selected_fish: return True
            
            max_temp_min = max(f.temp_min for f in selected_fish)
            min_temp_max = min(f.temp_max for f in selected_fish)
            max_ph_min = max(f.ph_min for f in selected_fish)
            min_ph_max = min(f.ph_max for f in selected_fish)
            
            return (max_temp_min <= min_temp_max) and (max_ph_min <= min_ph_max)

        def bioload_constraint(*counts):
            total_cm = sum(count * self.species_map[self.species_ids[i]].adult_size 
                          for i, count in enumerate(counts))
            return total_cm <= (self.volume / 2)

        def aggression_constraint(*counts):
            selected_fish = [self.species_map[self.species_ids[i]] 
                            for i, count in enumerate(counts) if count > 0]
            for i in range(len(selected_fish)):
                for j in range(i + 1, len(selected_fish)):
                    f1, f2 = selected_fish[i], selected_fish[j]
                    # Konflikt: Agresywna (3) z Łagodną (1)
                    if (f1.aggression_level == 3 and f2.aggression_level == 1) or \
                       (f2.aggression_level == 3 and f1.aggression_level == 1):
                        return False
            return True
        
        def solitary_species_constraint(*counts):
            has_solitary = False
            for i, count in enumerate(counts):
                if count > 0 and self.species_map[self.species_ids[i]].is_solitary:
                    has_solitary = True
                if count > 1: return False
                    
            if has_solitary and sum(counts) > 1:
                return False
            return True
                

        self.problem.addConstraint(diversity_constraint, self.species_ids)
        self.problem.addConstraint(water_compatibility_constraint, self.species_ids)
        self.problem.addConstraint(bioload_constraint, self.species_ids)
        self.problem.addConstraint(aggression_constraint, self.species_ids)
        self.problem.addConstraint(solitary_species_constraint, self.species_ids)

        start_time = time.perf_counter()
        solutions = self.problem.getSolutions()
        end_time = time.perf_counter()
        
        duration = end_time - start_time
        print(f"Sukces! Znaleziono {len(solutions)} propozycji w {duration:.2f}s")

        formatted_solutions = []
        for sol in solutions:
            item = []
            for f_id, count in sol.items():
                if count > 0:
                    fish_copy = copy.copy(self.species_map[f_id])
                    fish_copy.count = count 
                    item.append(fish_copy)
            formatted_solutions.append(item)

        return formatted_solutions, duration

# --- MODUŁ REGUŁOWY ---     

class RuleEngine:
    def __init__(self, solutions, volume, weights=None):
        self.solutions = solutions
        self.volume = volume
        self.weights = weights or {
            'zone_completeness': 20,
            'biomass_optimization': 30,
            'region_consistency': 25,
            'aggression_safety': 15
        }

    def score_and_rank(self):
        ranked_results = []
        for fish_list in self.solutions:
            score = 0
            reasons = []
            
            # 1. Strefy pływania
            occupied_zones = set(f.zone for f in fish_list)
            score += len(occupied_zones) * self.weights['zone_completeness']
            if len(occupied_zones) >= 2:
                reasons.append("Wypełnienie różnych stref")
            
            # 2. Wykorzystanie litrażu (biomasa)
            total_cm = sum(f.count * f.adult_size for f in fish_list)
            capacity_usage = total_cm / (self.volume / 2)
            
            # Bonus za "Złoty Środek" (70-90% obłożenia)
            if 0.7 <= capacity_usage <= 0.9:
                score += self.weights['biomass_optimization']
                reasons.append("Optymalne wypełnienie akwarium")

            # 3. Spójność geograficzna
            regions = [f.origin_region for f in fish_list if f.origin_region]
            if len(set(regions)) == 1:
                score += self.weights['region_consistency']
                reasons.append(f"Biotop: {regions[0]}")

            aggression_levels = [f.aggression_level for f in fish_list]
            max_aggression = max(aggression_levels) if aggression_levels else 1

            # 4. Agresja
            if max_aggression == 1:
                # Bonus dla obsady w pełni towarzyskiej
                score += self.weights['aggression_safety']
                reasons.append("Obsada bardzo łagodna")
            elif max_aggression == 2:
                # Mniejszy bonus lub brak kary dla ryb terytorialnych (opcjonalnie)
                score += (self.weights['aggression_safety'] * 0.5)
                reasons.append("Ryby o umiarkowanym temperamencie")

            # 5. Bonus za akwarium dla samotników
            if len(fish_list) == 1:
                fish = fish_list[0]
                score += 10
                reasons.append(f"Akwarium jednogatunkowe")
                if fish.is_solitary:
                    score += 20 
                    reasons.append(f"{fish.name} powinien żyć pojedynczo")

            ranked_results.append({
                'fish_details': [
                    {
                        'name': f.name, 
                        'count': f.count, 
                        'size_total': round(f.count * f.adult_size, 1),
                        'zone': f.get_zone_display(),
                        'origin_region': f.origin_region,
                        'source_url': f.source_url,
                        'aggression': f.aggression_level,
                    } for f in fish_list
                ],
                'total_score': round(score, 2),
                'capacity_usage_pct': round(capacity_usage * 100, 1),
                'reasons': reasons
            })

        # Zwracamy tylko najlepsze 50 wyników, żeby nie przeciążać widoku
        return sorted(ranked_results, key=lambda x: x['total_score'], reverse=True)[:50]