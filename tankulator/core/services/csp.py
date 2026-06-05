import time
import copy
from constraint import Problem
from ..models import FishSpecies
from .logger import log
from .experiment_logger import log_exp

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

        #regions = [f.origin_region for f in combo if f.origin_region]
        #if regions and len(set(regions)) == 1:
            #score += 15

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

        MAX_COMBINATIONS = 1000
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
        
        generated_combos = len(combos)

        log_exp(
            f"CSP_GENERATION;"
            f"VOLUME={self.volume};"
            f"CANDIDATES={len(self.candidates)};"
            f"GENERATED={generated_combos}"
        )

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

        selected_combos = len(combos)

        log_exp(
            f"CSP_HEURISTIC;"
            f"GENERATED={generated_combos};"
            f"SELECTED={selected_combos}"
        )

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
                bioload_per_fish = max(fish.bioload_index, 1)

                max_possible = max(
                    1,
                    int(self.volume / bioload_per_fish)
                )

                if fish.is_schooling:
                    possible_counts = [6, 8, 10, 12, 15, 20, 25, 30]
                else:
                    if self.volume >= 150:
                        possible_counts = [2, 6, 10]
                    else:
                        possible_counts = [2]

                possible_counts = [
                    c for c in possible_counts
                    if c <= max_possible
                ]

                if not possible_counts and not fish.is_schooling:
                    possible_counts = [min(max_possible, 2)]

                if self.base_fish and fish.id == self.base_fish.id:
                    domain = possible_counts
                else:
                    domain = [0] + possible_counts

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

                max_hardness_min = max(f.hardness_min for f in selected)
                min_hardness_max = min(f.hardness_max for f in selected)        

                ok = (
                        (max_temp_min <= min_temp_max)
                        and (max_ph_min <= min_ph_max)
                        and (max_hardness_min <= min_hardness_max)
                    )

                if not ok:
                    log(f"[FAIL water] {[f.name for f in selected]}")

                return ok

            def size_constraint(*counts):
                selected = [
                    species_map[species_ids[i]]
                    for i, c in enumerate(counts)
                    if c > 0
                ]

                for i in range(len(selected)):
                    for j in range(i + 1, len(selected)):

                        f1 = selected[i]
                        f2 = selected[j]

                        larger = max(f1.adult_size, f2.adult_size)
                        smaller = min(f1.adult_size, f2.adult_size)

                        # Ochrona małych ryb przed znacznie większymi gatunkami
                        if smaller <= 5 and larger >= smaller * 4:
                            return False

                        if larger <= 6:
                            continue

                        ratio_limit = (
                            3
                            if max(f1.aggression_level, f2.aggression_level) >= 3
                            else 5
                        )

                        if larger / smaller >= ratio_limit:
                            return False

                return True
            
            def bioload_constraint(*counts):
                total = sum(
                    counts[i] * species_map[species_ids[i]].bioload_index
                    for i in range(len(counts))
                )

                return total <= self.volume

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
            problem.addConstraint(size_constraint, species_ids)
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

        solve_time = end_time - start_time

        log_exp(
            f"CSP_SOLVE;"
            f"VOLUME={self.volume};"
            f"CANDIDATES={len(self.candidates)};"
            f"COMBINATIONS={selected_combos};"
            f"SOLUTIONS={len(all_solutions)};"
            f"TIME={solve_time:.6f}"
        )

        log(f"Znaleziono {len(all_solutions)} rozwiązań w {end_time - start_time:.2f}s")

        return all_solutions, solve_time