class RuleContext:
    def __init__(self, fish_list, volume, base_fish_id):
        self.fish_list = fish_list
        self.volume = volume
        self.base_fish_id = base_fish_id

        self.fish_ids = [f.id for f in fish_list]
        self.zones = set(f.zone for f in fish_list)
        self.regions = [f.origin_region for f in fish_list if f.origin_region]

        total_bioload = sum(
            f.count * f.bioload_index
            for f in fish_list
        )

        self.capacity_usage = total_bioload / volume if volume else 0

        self.species_count = len(fish_list)

        self.total_fish_count = sum(
            f.count for f in fish_list
        )

        self.schooling_species_count = sum(
            1 for f in fish_list
            if f.is_schooling
        )

        self.schooling_fish = [
            f for f in fish_list
            if f.is_schooling
        ]