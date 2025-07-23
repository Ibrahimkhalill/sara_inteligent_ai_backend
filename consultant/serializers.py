from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import  ConsultantFarm, ConsultantRequest
from authentications.models import UserProfile


User = get_user_model()

class UserProfileSerializer(serializers.ModelSerializer):
  

    class Meta:
        model = UserProfile
        fields = ['name', 'phone_number', 'profile_picture', 'joined_date']
        read_only_fields = ['joined_date']

class FarmSerializer(serializers.ModelSerializer):
  
    profile = UserProfileSerializer(source='user_profile', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'profile']

class ConsultantRequestSerializer(serializers.ModelSerializer):
    consultant_email = serializers.EmailField(source='consultant.email', read_only=True)
    consultant_name = serializers.CharField(source='consultant.user_profile.name', read_only=True, allow_null=True)
    farm_email = serializers.EmailField(source='farm.email', read_only=True)
    farm_name = serializers.CharField(source='farm.user_profile.name', read_only=True, allow_null=True)
    consultant_profile_picture = serializers.ImageField(source='consultant.user_profile.profile_picture', read_only=True, allow_null=True) 
    farm_profile_picture = serializers.ImageField(source='farm.user_profile.profile_picture', read_only=True, allow_null=True) 
    class Meta:
        model = ConsultantRequest
        fields = ['id', 'farm', 'farm_email', 'farm_name', 'farm_profile_picture', 'consultant', 'consultant_email', 'consultant_name','consultant_profile_picture', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'farm_email', 'farm_name', 'consultant_email', 'consultant_name', 'created_at', 'updated_at']

    def validate(self, data):
        errors = {}
        farm = data.get('farm')
        consultant = data.get('consultant')

        if not farm:
            errors['farm'] = ['This field is required']
        elif farm.role != 'farm':
            errors['farm'] = ['Selected user must have role "farm"']

        if not consultant:
            errors['consultant'] = ['This field is required']
        elif consultant.role != 'consultant':
            errors['consultant'] = ['Selected user must have role "consultant"']

        if farm == consultant:
            errors['non_field_errors'] = ['Farm and consultant cannot be the same user']

        if ConsultantFarm.objects.filter(farm=farm, consultant=consultant, is_active=True).exists():
            errors['non_field_errors'] = ['This consultant is already associated with the farm']

        if ConsultantRequest.objects.filter(farm=farm, consultant=consultant, status='pending').exists():
            errors['non_field_errors'] = ['A pending request already exists for this consultant and farm']

        if errors:
            raise serializers.ValidationError(errors)
        return data

class ConsultantFarmSerializer(serializers.ModelSerializer):
    farm_email = serializers.EmailField(source='farm.email', read_only=True)
    farm_name = serializers.CharField(source='farm.user_profile.name', read_only=True, allow_null=True)
    consultant_email = serializers.EmailField(source='consultant.email', read_only=True)
    consultant_name = serializers.CharField(source='consultant.user_profile.name', read_only=True, allow_null=True)
    consultant_profile = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ConsultantFarm
        fields = ['id', 'farm', 'farm_email', 'farm_name', 'consultant', 'consultant_email', 'consultant_name', 'consultant_profile', 'created_at', 'is_active']
        read_only_fields = ['id', 'farm_email', 'farm_name', 'consultant_email', 'consultant_name', 'consultant_profile', 'created_at', 'is_active']

    def get_consultant_profile(self, obj):
        try:
            profile = obj.consultant.user_profile
            return UserProfileSerializer(profile).data
        except UserProfile.DoesNotExist:
            return None
