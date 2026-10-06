# bookings/serializers.py
from rest_framework import serializers
from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['id', 'user', 'booking_type',
                  'location', 'booking_datetime', 'booking_end_date', 'created_at']
        read_only_fields = ['id', 'created_at', 'user']  # 👈 user is read-only now

    def validate(self, data):
        start = data.get('booking_datetime', getattr(self.instance, 'booking_datetime', None))
        end = data.get('booking_end_date', getattr(self.instance, 'booking_end_date', None))
        if start and end and end < start:
            raise serializers.ValidationError({"booking_end_date": ["End date must be after the booking date"]})
        return data
