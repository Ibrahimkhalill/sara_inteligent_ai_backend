from rest_framework import serializers
from rest_framework import serializers
from .models import SubscriptionPlan, Description
from authentications.serializers import CustomUserSerializer
from .models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = '__all__'


class DescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Description
        fields = ['id', 'text', 'created_at']

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    descriptions = DescriptionSerializer(many=True, read_only=True)

    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'price_id', 'name', 'amount', 'duration_type', 'descriptions', 'created_at', 'updated_at']
