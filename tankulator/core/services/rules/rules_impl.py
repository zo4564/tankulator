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
    if params["min"] <= ctx.capacity_usage <= params["max"]:
        return 1, "Optymalne wypełnienie akwarium", None
    return 0, None, None

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

  