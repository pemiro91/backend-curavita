from django.contrib import admin

from apps.services.models import Specialty


# Register your models here.

@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    pass