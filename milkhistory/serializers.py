from rest_framework import serializers
from .models import MilkHistory
from Member.models import Member
from django.contrib.auth import get_user_model

User = get_user_model()

class MilkHistorySerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    farm_email = serializers.EmailField(source='farm.email', read_only=True)

    class Meta:
        model = MilkHistory
        fields = [
            'id', 'user', 'user_email', 'farm', 'farm_email', 'created_at',
            'bottle_size', 'number_of_bottles', 'hospital_solids',
            'hospital_milk_volume', 'desired_solids_content',
            'pounds_of_water', 'pounds_of_milk_replacer',
            'solids_hospital_milk', 'hospital_milk_used', 'total_volume'
        ]
        read_only_fields = ['id', 'user', 'user_email', 'farm', 'farm_email', 'created_at']

    def validate(self, data):
        errors = {}
        # Ensure non-negative values for numeric fields
        for field in [
            'bottle_size', 'hospital_solids', 'hospital_milk_volume',
            'desired_solids_content', 'pounds_of_water',
            'pounds_of_milk_replacer', 'solids_hospital_milk',
            'hospital_milk_used'
        ]:
            if field in data and data[field] is not None and data[field] < 0:
                errors[field] = [f'{field.replace("_", " ").title()} cannot be negative']
        
        # Ensure number_of_bottles is positive
        if 'number_of_bottles' in data and data['number_of_bottles'] <= 0:
            errors['number_of_bottles'] = ['Number of bottles must be greater than zero']

        # Ensure at least one measurement field is provided
        measurement_fields = [
            data.get('bottle_size'), data.get('number_of_bottles'),
            data.get('hospital_solids'), data.get('hospital_milk_volume'),
            data.get('desired_solids_content'), data.get('pounds_of_water'),
            data.get('pounds_of_milk_replacer'), data.get('solids_hospital_milk'),
            data.get('hospital_milk_used'), data.get('total_volume')
        ]
        if not any(field is not None for field in measurement_fields):
            errors['non_field_errors'] = ['At least one measurement field must be provided']

        if errors:
            raise serializers.ValidationError(errors)
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated or request.user.role not in ['farm', 'farm_user']:
            raise serializers.ValidationError({'user': ['Must be an authenticated farm or farm user']})
        
        validated_data['user'] = request.user
        if request.user.role == 'farm':
            validated_data['farm'] = request.user
        else:  # farm_user
            member = Member.objects.filter(farm_user=request.user, is_active=True).first()
            if not member:
                raise serializers.ValidationError({'farm': ['User is not an active member of any farm']})
            validated_data['farm'] = member.farm
        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated or request.user.role not in ['farm', 'farm_user']:
            raise serializers.ValidationError({'user': ['Must be an authenticated farm or farm user']})
        
        # Ensure the user matches the instance and farm is consistent
        if instance.user != request.user:
            raise serializers.ValidationError({'user': ['Cannot update another user’s record']})
        
        if request.user.role == 'farm':
            if instance.farm != request.user:
                raise serializers.ValidationError({'farm': ['Farm user must set farm field to themselves']})
        else:  # farm_user
            member = Member.objects.filter(farm_user=request.user, is_active=True).first()
            if not member or member.farm != instance.farm:
                raise serializers.ValidationError({'farm': ['Cannot change farm or user is not a member of this farm']})
        
        return super().update(instance, validated_data)