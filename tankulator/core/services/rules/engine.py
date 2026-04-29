from .loader import RuleLoader
from .context import RuleContext
from .registry import RULE_REGISTRY
from ..logger import log
from . import rules_impl

class RuleEngine:
    def __init__(self, solutions, volume, base_fish_id=None, rules_path="rules.json"):
        self.solutions = solutions
        self.volume = volume
        self.base_fish_id = base_fish_id

        self.rules = RuleLoader(rules_path).load()

    def score_and_rank(self):
        ranked_results = []

        log("\n=== START SCORING ===")

        for idx, fish_list in enumerate(self.solutions):
            fish_list = [f for f in fish_list if f.count > 0]
            if not fish_list:
                continue

            ctx = RuleContext(fish_list, self.volume, self.base_fish_id)

            score = 0
            reasons = []
            has_base = False

            log(f"\n--- Solution #{idx} ---")

            for rule in self.rules:
                rule_type = rule["type"]
                weight = rule.get("weight", 1)
                params = rule.get("params", {})

                if rule_type not in RULE_REGISTRY:
                    continue

                base_score, reason, base_flag = RULE_REGISTRY[rule_type](ctx, params)

                final_score = base_score * weight
                score += final_score

                if reason and final_score > 0:
                    reasons.append(reason)

                if rule_type == "base_fish":
                    has_base = base_flag

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
                'capacity_usage_pct': round(ctx.capacity_usage * 100, 1),
                'reasons': reasons,
                'has_base_fish': has_base
            })

        sorted_results = sorted(
            ranked_results,
            key=lambda x: (x['has_base_fish'], x['total_score']),
            reverse=True
        )

        return sorted_results[:50]