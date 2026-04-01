from django.contrib import admin
from .models import FishSpecies

@admin.register(FishSpecies)
class FishSpeciesAdmin(admin.ModelAdmin):
    list_display = ('name', 'temp_min', 'temp_max', 'ph_min', 'ph_max', 'min_tank_volume')