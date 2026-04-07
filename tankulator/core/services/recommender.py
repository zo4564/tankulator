import time
import copy
from constraint import Problem
from ..models import FishSpecies
import logging

# --- LOGGER ---
logging.basicConfig(
    filename='aquarium_debug.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    encoding='utf-8'
)

def log(msg):
    logging.info(msg)

# --- PREPROCESSING ---

class AquariumEngine:
    def __init__(self, volume, temp=None, ph=None, hardness=None, base_fish=None):
        self.volume = volume
        self.temp = temp
        self.ph = ph
        self.hardness = hardness
        self.base_fish = base_fish

    def compatibility_score(self, f1, f2):
        score = 0

        overlap = min(f1.temp_max, f2.temp_max) - max(f1.temp_min, f2.temp_min)
        score += max(0, overlap)

        overlap_ph = min(f1.ph_max, f2.ph_max) - max(f1.ph_min, f2.ph_min)
        score += max(0, overlap_ph)

        score -= abs(f1.aggression_level - f2.aggression_level) * 3

        return score

    def get_filtered_candidates(self, use_preprocessing=True):
        start_time = time.perf_counter()
        candidates = FishSpecies.objects.all()
        
        if use_preprocessing:
            candidates = candidates.filter(min_tank_volume__lte=self.volume)

            if self.temp:
                candidates = candidates.filter(temp_min__lte=self.temp, temp_max__gte=self.temp)
            if self.ph:
                candidates = candidates.filter(ph_min__lte=self.ph, ph_max__gte=self.ph)

            candidates = list(candidates)

            estimated_max_length = (self.volume ** (1/3)) * 4 
            candidates = [f for f in candidates if f.adult_size <= estimated_max_length]

            final_candidates = []
            for f in candidates:
                min_qty = 6 if f.is_schooling else 1
                if (f.adult_size * min_qty) <= (self.volume / 2):
                    final_candidates.append(f)

            if self.base_fish:
                if self.base_fish not in final_candidates:
                    final_candidates.append(self.base_fish)

                final_candidates = sorted(
                    final_candidates,
                    key=lambda f: self.compatibility_score(self.base_fish, f),
                    reverse=True
                )[:30]

                if len(final_candidates) < 5:
                    final_candidates = sorted(
                        candidates,
                        key=lambda f: self.compatibility_score(self.base_fish, f),
                        reverse=True
                    )[:20]

            else:
                if len(final_candidates) > 50:
                    target_ph = self.ph if self.ph else 7.0
                    final_candidates = sorted(
                        final_candidates,
                        key=lambda f: abs(((f.ph_min + f.ph_max) / 2) - target_ph)
                    )[:50]

        if self.base_fish:
            if self.base_fish.id not in [f.id for f in final_candidates]:
                final_candidates.append(self.base_fish)

        end_time = time.perf_counter()
        return final_candidates, (end_time - start_time)
    

# --- MODUŁ CSP ---

class AquariumCSP:
    def __init__(self, candidates, volume, base_fish=None):
        self.problem = Problem()
        self.candidates = list(candidates)
        self.volume = volume
        self.base_fish = base_fish
        self.species_ids = [f.id for f in self.candidates]
        self.species_map = {f.id: f for f in self.candidates}

    def score_combination(self, combo):
        score = 0

        max_temp_min = max(f.temp_min for f in combo)
        min_temp_max = min(f.temp_max for f in combo)

        max_ph_min = max(f.ph_min for f in combo)
        min_ph_max = min(f.ph_max for f in combo)

        score += 20 if max_temp_min <= min_temp_max else -50
        score += 20 if max_ph_min <= min_ph_max else -50

        zones = set(f.zone for f in combo)
        score += len(zones) * 10

        for i in range(len(combo)):
            for j in range(i + 1, len(combo)):
                if abs(combo[i].aggression_level - combo[j].aggression_level) >= 2:
                    score -= 20

        regions = [f.origin_region for f in combo if f.origin_region]
        if regions and len(set(regions)) == 1:
            score += 15

        score += sum(1 for f in combo if f.is_schooling) * 5

        return score

    def solve(self):
        if not self.candidates:
            return [], 0

        log(f"Kandydaci: {len(self.candidates)}")

        if self.base_fish:
            log(f"Base fish: {self.base_fish.name} (id={self.base_fish.id})")
            present = any(f.id == self.base_fish.id for f in self.candidates)
            log(f"Czy base fish w candidates? {present}")

        seen = set()
        start_time = time.perf_counter()
        all_solutions = []

        MAX_COMBINATIONS = 500
        MAX_SOLUTIONS = 1000

        from itertools import combinations

        combos = []
        for k in range(2, 4):
            all_combos = list(combinations(self.candidates, k))

            if self.base_fish:
                all_combos = [
                    combo for combo in all_combos
                    if any(f.id == self.base_fish.id for f in combo)
                ]

            combos.extend(all_combos)

        # DEBUG combos
        if self.base_fish:
            combos_with_base = [
                combo for combo in combos
                if any(f.id == self.base_fish.id for f in combo)
            ]
            log(f"Combos z base fish: {len(combos_with_base)} / {len(combos)}")

        scored_combos = [
            (combo, self.score_combination(combo))
            for combo in combos
        ]

        scored_combos.sort(key=lambda x: x[1], reverse=True)

        combos = [combo for combo, score in scored_combos[:MAX_COMBINATIONS]]

        log(f"Testujemy {len(combos)} kombinacji")

        # DEBUG TOP combos
        if self.base_fish:
            combos_with_base = [
                combo for combo in combos
                if any(f.id == self.base_fish.id for f in combo)
            ]
            log(f"TOP combos z base fish: {len(combos_with_base)}")

        for combo in combos:

            problem = Problem()
            species_ids = [f.id for f in combo]
            species_map = {f.id: f for f in combo}

            for fish in combo:
                bioload_per_fish = fish.adult_size if fish.adult_size > 0 else 5
                max_possible = int((self.volume / 2) / bioload_per_fish)

                if self.base_fish and fish.id == self.base_fish.id:
                    # base fish 
                    if fish.is_schooling:
                        domain = [6, 10, 15, 20, 25, 30]
                    else:
                        domain = [1]
                        if max_possible >= 2:
                            domain.append(2)
                else:
                    if fish.is_schooling:
                        domain = [0, 6, 10, 15, 20, 25, 30]
                    else:
                        domain = [0, 1]
                        if max_possible >= 2:
                            domain.append(2)

                problem.addVariable(fish.id, domain)

            # --- CONSTRAINTY ---

            def water_constraint(*counts):
                selected = [species_map[species_ids[i]]
                            for i, c in enumerate(counts) if c > 0]

                if not selected:
                    return True

                max_temp_min = max(f.temp_min for f in selected)
                min_temp_max = min(f.temp_max for f in selected)
                max_ph_min = max(f.ph_min for f in selected)
                min_ph_max = min(f.ph_max for f in selected)

                ok = (max_temp_min <= min_temp_max) and (max_ph_min <= min_ph_max)

                if not ok:
                    log(f"[FAIL water] {[f.name for f in selected]}")

                return ok

            def bioload_constraint(*counts):
                total = sum(
                    counts[i] * species_map[species_ids[i]].adult_size
                    for i in range(len(counts))
                )
                return total <= (self.volume / 2)

            def aggression_constraint(*counts):
                selected = [species_map[species_ids[i]]
                            for i, c in enumerate(counts) if c > 0]

                for i in range(len(selected)):
                    for j in range(i + 1, len(selected)):
                        f1, f2 = selected[i], selected[j]
                        if (f1.aggression_level == 3 and f2.aggression_level == 1) or \
                           (f2.aggression_level == 3 and f1.aggression_level == 1):
                            return False
                return True

            def solitary_constraint(*counts):
                has_solitary = False

                for i, c in enumerate(counts):
                    fish = species_map[species_ids[i]]

                    if c > 0 and fish.is_solitary:
                        has_solitary = True

                    if fish.is_solitary and c > 1:
                        return False

                if has_solitary and sum(counts) > 1:
                    return False

                return True

            problem.addConstraint(water_constraint, species_ids)
            problem.addConstraint(bioload_constraint, species_ids)
            problem.addConstraint(aggression_constraint, species_ids)
            problem.addConstraint(solitary_constraint, species_ids)

            for sol in problem.getSolutionIter():

                # DEBUG: czy solution zawiera base fish
                if self.base_fish:
                    has_base = any(
                        species_map[f_id].id == self.base_fish.id and count > 0
                        for f_id, count in sol.items()
                    )
                    if has_base:
                        log(f"Solution with base fish: {sol}")

                result = []
                for f_id, count in sol.items():
                    if count > 0:
                        fish_copy = copy.copy(species_map[f_id])
                        fish_copy.count = count
                        result.append(fish_copy)

                if result:
                    signature = tuple(sorted((f.id, f.count) for f in result))

                    if signature not in seen:
                        seen.add(signature)
                        all_solutions.append(result)

                if len(all_solutions) >= MAX_SOLUTIONS:
                    break

            if len(all_solutions) >= MAX_SOLUTIONS:
                break

        end_time = time.perf_counter()

        log(f"Znaleziono {len(all_solutions)} rozwiązań w {end_time - start_time:.2f}s")

        return all_solutions, (end_time - start_time)

# --- MODUŁ REGUŁOWY ---     

class RuleEngine:
    def __init__(self, solutions, volume, base_fish_id=None, weights=None):
        self.solutions = solutions
        self.volume = volume
        self.base_fish_id = base_fish_id

        self.weights = weights or {
            'zone_completeness': 200,
            'biomass_optimization': 15,
            'region_consistency': 15,
            'aggression_safety': 0,
            'base_fish_bonus': 500,     # DUŻY BOOST
            'base_fish_penalty': -1000  # JESZCZE WIĘKSZA KARA
        }

    def score_and_rank(self):
        ranked_results = []

        log("\n=== START SCORING ===")

        for idx, fish_list in enumerate(self.solutions):
            # USUWAMY ryby z count = 0
            fish_list = [f for f in fish_list if f.count > 0]

            if not fish_list:
                continue

            score = 0
            reasons = []

            fish_ids = [f.id for f in fish_list]

            # --- DEBUG ---
            log(f"\n--- Solution #{idx} ---")
            log(f"Fish IDs: {fish_ids}")

            # 0. BASE FISH PRIORYTET
            has_base = self.base_fish_id in fish_ids if self.base_fish_id else False

            log(f"Has base fish: {has_base}")

            if self.base_fish_id:
                if has_base:
                    score += self.weights['base_fish_bonus']
                    reasons.append("Zawiera wybraną rybę (priorytet)")
                else:
                    score += self.weights['base_fish_penalty']
                    reasons.append("Brak wybranej ryby (kara)")

            # 1. Strefy pływania
            occupied_zones = set(f.zone for f in fish_list)
            zone_score = len(occupied_zones) * self.weights['zone_completeness']
            score += zone_score

            log(f"Zones: {occupied_zones}, score: {zone_score}")

            if len(occupied_zones) >= 2:
                reasons.append("Wypełnienie różnych stref")

            # 2. Biomasa
            total_cm = sum(f.count * f.adult_size for f in fish_list)

            if self.volume > 0:
                capacity_usage = total_cm / (self.volume / 2)
            else:
                capacity_usage = 0

            log(f"Capacity usage: {round(capacity_usage, 2)}")

            if 0.7 <= capacity_usage <= 0.9:
                score += self.weights['biomass_optimization']
                reasons.append("Optymalne wypełnienie akwarium")

            # 3. Region
            regions = [f.origin_region for f in fish_list if f.origin_region]

            if regions:
                unique_regions = set(regions)
                log(f"Regions: {unique_regions}")

                if len(unique_regions) == 1:
                    score += self.weights['region_consistency']
                    reasons.append(f"Biotop: {regions[0]}")

            # 4. Agresja
            aggression_levels = [f.aggression_level for f in fish_list]
            max_aggression = max(aggression_levels) if aggression_levels else 1

            log(f"Max aggression: {max_aggression}")

            if max_aggression == 1:
                score += self.weights['aggression_safety']
                reasons.append("Obsada bardzo łagodna")
            elif max_aggression == 2:
                score += (self.weights['aggression_safety'] * 0.5)
                reasons.append("Ryby o umiarkowanym temperamencie")

            # 5. Samotniki
            if len(fish_list) == 1:
                fish = fish_list[0]
                if fish.is_solitary:
                    score += 20
                    reasons.append(f"{fish.name} powinien żyć pojedynczo")

            log(f"FINAL SCORE: {score}")

            ranked_results.append({
                'fish_details': [
                    {
                        'id': f.id,
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
                'reasons': reasons,
                'has_base_fish': has_base
            })

        log("\n=== SORTOWANIE ===")

        sorted_results = sorted(
            ranked_results,
            key=lambda x: (x['has_base_fish'], x['total_score']),
            reverse=True
        )

        log("\nTOP 5 PO SORTOWANIU:")
        for r in sorted_results[:5]:
            log(f"{[f['name'] for f in r['fish_details']]} | score: {r['total_score']} | base: {r['has_base_fish']}")

        return sorted_results[:50]