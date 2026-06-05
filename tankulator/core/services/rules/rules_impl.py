from .registry import register_rule

@register_rule("base_fish")
def rule_base(ctx, params):
    if not ctx.base_fish_id:
        return 0, None, False

    has_base = ctx.base_fish_id in ctx.fish_ids

    if has_base:
        return params["bonus"], "Zawiera wybraną rybę (priorytet)", True
    else:
        return params["penalty"], "Brak wybranej ryby (kara)", False
    
@register_rule("zones")
def rule_zones(ctx, params):
    score = len(ctx.zones)
    reason = "Wypełnienie różnych stref" if score >= 2 else None
    return score, reason, None
    
@register_rule("biomass")
def rule_biomass(ctx, params):
    target = 0.85
    tolerance = 0.05
    diff = abs(ctx.capacity_usage - target)
    score = max(0, 1 - diff / tolerance)
    return score, "Optymalne zapełnienie akwarium", None

@register_rule("region")
def rule_region(ctx, params):
    if ctx.regions and len(set(ctx.regions)) == 1:
        return 1, f"Biotop: {ctx.regions[0]}", None
    return 0, None, None

@register_rule("aggression")
def rule_aggression(ctx, params):
    levels = [f.aggression_level for f in ctx.fish_list]
    if not levels:
        return 0, None, None

    max_aggr = max(levels)

    if max_aggr == 1:
        return 1, "Obsada bardzo łagodna", None
    elif max_aggr == 2:
        return 0.5, "Ryby o umiarkowanym temperamencie", None

    return 0, None, None

@register_rule("solitary")
def rule_solitary(ctx, params):
    if len(ctx.fish_list) == 1:
        fish = ctx.fish_list[0]
        if fish.is_solitary:
            return 1, f"{fish.name} powinien żyć pojedynczo", None
    return 0, None, None

  
@register_rule("diversity")
def rule_diversity(ctx, params):
    counts = [f.count for f in ctx.fish_list if f.count > 0]
    if len(counts) < 3:
        return 0, None, None
    ratio = min(counts) / max(counts)
    species_score = min(len(counts) / 3, 1)
    score = ratio * species_score
    if score > 0.2:
        return score, "Różnorodność gatunków", None
    else:
        return score, None, None

@register_rule("school_size")
def rule_school_size(ctx, params):
    if not ctx.schooling_fish:
        return 0, None, None
    scores = []
    for fish in ctx.schooling_fish:
        if fish.count < 12:
            scores.append(0)
            continue
        target_school = max(
            12,
            int(
                ctx.volume /
                (fish.adult_size * 2)
            )
        )
        ratio = fish.count / target_school
        score = min(ratio, 1)
        scores.append(score)
    final_score = sum(scores) / len(scores)
    reason = None
    if final_score >= 0.9:
        reason = "Duże, naturalne stada"
    return final_score, reason, None