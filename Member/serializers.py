from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Member
from django.db import transaction
from authentications.models import UserProfile
User = get_user_model()

class MemberSerializer(serializers.ModelSerializer):
    farm_email = serializers.EmailField(source='farm.email', read_only=True)
    farm_user_email = serializers.EmailField(source='farm_user.email', read_only=True)
    # Fields for creating a new farm_user
    email = serializers.EmailField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True)
    name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Member
        fields = [
            'id', 'farm', 'farm_email', 'farm_user', 'farm_user_email',
            'created_at', 'is_active', 'email', 'password', 'name', 'phone_number'
        ]
        read_only_fields = ['id', 'farm_user', 'farm_user_email', 'created_at', 'is_active']

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
                is_active=True,  # Set to False if email verification is required
                is_verified=True  # Adjust based on your verification flow
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