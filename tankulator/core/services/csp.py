import time
import copy
from constraint import Problem
from ..models import FishSpecies
from .logger import log

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