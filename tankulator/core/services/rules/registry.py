RULE_REGISTRY = {}

def register_rule(name):
    def decorator(fn):
        RULE_REGISTRY[name] = fn
        return fn
    return decorator