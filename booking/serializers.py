# bookings/serializers.py
from rest_framework import serializers
from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['id', 'user', 'booking_type',
                  'location', 'booking_datetime', 'booking_end_date', 'created_at']
        read_only_fields = ['id', 'created_at', 'user']  # 👈 user is read-only now

