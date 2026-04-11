# apps/services/serializers.py
from rest_framework import serializers

from .models import Specialty, Service


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ['id', 'name', 'slug', 'description', 'icon', 'color']


class ServiceSerializer(serializers.ModelSerializer):
    specialty_name = serializers.CharField(source='specialty.name', read_only=True)

    class Meta:
        model = Service
        fields = [
            'id', 'name', 'description', 'service_type',
            'price', 'duration_minutes', 'specialty_name',
            'requires_preparation', 'is_active'
        ]


class ServiceDetailSerializer(serializers.ModelSerializer):
    specialty = SpecialtySerializer(read_only=True)
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)

    class Meta:
        model = Service
        fields = [
            'id', 'name', 'description', 'service_type',
            'price', 'duration_minutes', 'specialty',
            'clinic_name', 'requires_preparation',
            'preparation_instructions', 'is_active'
        ]