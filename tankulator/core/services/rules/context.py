class RuleContext:
    def __init__(self, fish_list, volume, base_fish_id):
        self.fish_list = fish_list
        self.volume = volume
        self.base_fish_id = base_fish_id

        self.fish_ids = [f.id for f in fish_list]
        self.zones = set(f.zone for f in fish_list)
        self.regions = [f.origin_region for f in fish_list if f.origin_region]

        total_cm = sum(f.count * f.adult_size for f in fish_list)
        self.capacity_usage = total_cm / (volume / 2) if volume else 0