from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Member
from authentications.models import UserProfile
from django.db import transaction

User = get_user_model()

class UserProfileSerializer(serializers.ModelSerializer):
   

    class Meta:
        model = UserProfile
        fields = ['name', 'phone_number', 'profile_picture', 'joined_date']
        read_only_fields = ['joined_date']

class MemberSerializer(serializers.ModelSerializer):
    member_id = serializers.IntegerField(source='id', read_only=True)
    farm_id = serializers.IntegerField(source='farm.id', read_only=True)
    farm_user_id = serializers.IntegerField(source='farm_user.id', read_only=True)
    farm_email = serializers.EmailField(source='farm.email', read_only=True)
    farm_name = serializers.CharField(source='farm.user_profile.name', read_only=True, allow_null=True)
    farm_user_email = serializers.EmailField(source='farm_user.email', read_only=True)
    farm_user_profile = serializers.SerializerMethodField(read_only=True)
    # Fields for creating a new farm_user
    email = serializers.EmailField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True)
    name = serializers.CharField(write_only=True, required=True, allow_blank=True)
    phone_number = serializers.CharField(write_only=True, required=True, allow_blank=True)
    profile_picture = serializers.ImageField(write_only=True, required=True, allow_null=True)

    class Meta:
        model = Member
        fields = [
            'member_id', 'farm_id', 'farm_email', 'farm_name', 'farm_user_id', 'farm_user_email', 'farm_user_profile',
            'created_at', 'is_active', 'email', 'password', 'name', 'phone_number', 'profile_picture'
        ]
        read_only_fields = ['member_id', 'farm_id', 'farm_user_id', 'farm_email', 'farm_name', 'farm_user_email', 'farm_user_profile', 'created_at', 'is_active']

    def get_farm_user_profile(self, obj):
        try:
            profile = obj.farm_user.user_profile
            return UserProfileSerializer(profile).data
        except UserProfile.DoesNotExist:
            return None

    def validate(self, data):
        errors = {}
        farm = data.get('farm')
        email = data.get('email')

        # Validate farm
        if not farm:
            errors['farm'] = ['This field is required']
        elif farm.role != 'farm':
            errors['farm'] = ['Selected user must have role "farm"']

        # Check if email is already in use
        if email and User.objects.filter(email=email).exists():
            errors['email'] = ['A user with this email already exists']

        if errors:
            raise serializers.ValidationError(errors)
        return data

    def create(self, validated_data):
        # Extract user creation fields
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        name = validated_data.pop('name', '')
      

        # Create user and member in a transaction
        with transaction.atomic():
            # Create CustomUser with role 'farm_user'
            user = User.objects.create_user(
                email=email,
                password=password,
                role='farm_user',
                is_active=True,  # Set to True for email verification
                is_verified=True  # Require OTP verification
            )

            # Create UserProfile
            UserProfile.objects.create(
                user=user,
                name=name,
               
            )

            # Create Member
            validated_data['farm_user'] = user
            member = super().create(validated_data)
            return member