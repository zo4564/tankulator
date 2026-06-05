import time
import copy
from constraint import Problem
from ..models import FishSpecies
from .experiment_logger import log_exp

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
                candidates = candidates.filter(
                    temp_min__lte=self.temp, 
                    temp_max__gte=self.temp)
            if self.ph:
                candidates = candidates.filter(
                    ph_min__lte=self.ph, 
                    ph_max__gte=self.ph)
            if self.hardness:
                candidates = candidates.filter(
                    hardness_min__lte=self.hardness,
                    hardness_max__gte=self.hardness
    )

            candidates = list(candidates)

            estimated_max_length = (self.volume ** (1/3)) * 4 
            candidates = [f for f in candidates if f.adult_size <= estimated_max_length]

            final_candidates = []
            for f in candidates:
                min_qty = 6 if f.is_schooling else 1

                if (f.bioload_index * min_qty) <= self.volume * 1.5:
                    final_candidates.append(f)

            if self.base_fish:
                if self.base_fish not in final_candidates:
                    final_candidates.append(self.base_fish)

                final_candidates = sorted(
                    final_candidates,
                    key=lambda f: self.compatibility_score(self.base_fish, f),
                    reverse=True
                )[:300]

                if len(final_candidates) < 5:
                    final_candidates = sorted(
                        candidates,
                        key=lambda f: self.compatibility_score(self.base_fish, f),
                        reverse=True
                    )[:200]

            else:
                if len(final_candidates) > 50:
                    target_ph = self.ph if self.ph else 7.0
                    final_candidates = sorted(
                        final_candidates,
                        key=lambda f: abs(((f.ph_min + f.ph_max) / 2) - target_ph)
                    )[:100]

        if self.base_fish:
            if self.base_fish.id not in [f.id for f in final_candidates]:
                final_candidates.append(self.base_fish)

        end_time = time.perf_counter()
        log_exp(
            f"PREPROCESS;"
            f"VOLUME={self.volume};"
            f"CANDIDATES={len(final_candidates)};"
            f"TIME={end_time-start_time:.6f}"
        )
        return final_candidates, (end_time - start_time)