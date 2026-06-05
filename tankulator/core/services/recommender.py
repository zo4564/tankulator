from .preprocessing import AquariumEngine
from .csp import AquariumCSP
from .rules.engine import RuleEngine

import os
from django.conf import settings


RULES_PATH = os.path.join(
    settings.BASE_DIR,
    "core",
    "services",
    "rules",
    "rules.json"
)


class RecommenderService:
    def __init__(self, volume, temp=None, ph=None, hardness=None, base_fish=None):
        self.volume = volume
        self.temp = temp
        self.ph = ph
        self.hardness = hardness
        self.base_fish = base_fish

    def run(self):
        # --- 1. PREPROCESSING ---
        engine = AquariumEngine(
            volume=self.volume,
            temp=self.temp,
            ph=self.ph,
            hardness=self.hardness,
            base_fish=self.base_fish
        )

        candidates, prep_time = engine.get_filtered_candidates()
        
        print("KANDYDACI:", len(candidates))

        # --- 2. CSP ---
        csp = AquariumCSP(
            candidates=candidates,
            volume=self.volume,
            base_fish=self.base_fish
        )

        solutions, csp_time = csp.solve()

        # --- 3. RULE ENGINE ---
        rule_engine = RuleEngine(
            solutions=solutions,
            volume=self.volume,
            base_fish_id=self.base_fish.id if self.base_fish else None,
            rules_path=RULES_PATH
        )

        ranked = rule_engine.score_and_rank()

        # --- 4. META INFO ---
        return {
            "results": ranked,
            "meta": {
                "candidates_count": len(candidates),
                "solutions_count": len(solutions),
                "preprocessing_time": round(prep_time, 3),
                "csp_time": round(csp_time, 3)
            }
        }