from django.db import models

class FishSpecies(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nazwa gatunku")
    latin_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nazwa łacińska")
    temp_min = models.FloatField(help_text="Minimalna temperatura [°C]")
    temp_max = models.FloatField(help_text="Maksymalna temperatura [°C]")
    ph_min = models.FloatField(help_text="Minimalne pH")
    ph_max = models.FloatField(help_text="Maksymalne pH")
    hardness_min = models.FloatField(default=5.0, help_text="Minimalna twardość [dH]")
    hardness_max = models.FloatField(default=15.0, help_text="Maksymalna twardość [dH]")
    min_tank_volume = models.PositiveIntegerField(help_text="Minimalny litraż [L]")
    bioload_index = models.FloatField(help_text="Współczynnik obciążenia biologicznego")
    is_schooling = models.BooleanField(default=False)
    adult_size = models.FloatField(default=5.0)
    origin_region = models.CharField(max_length=100, blank=True)
    
    WATER_ZONE_CHOICES = [
        ('TOP', 'Tafle wody'),
        ('MID', 'Środkowe partie'),
        ('BTM', 'Przy dnie'),
    ]
    zone = models.CharField(max_length=3, choices=WATER_ZONE_CHOICES, default='MID')
    aggression_level = models.IntegerField(default=1, help_text="Poziom agresji (1-3)")

    def __str__(self):
        return self.name