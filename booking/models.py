from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Booking(models.Model):
    BOOKING_TYPES = [
        ("flight", "Flight Booking"),
        ("restaurant", "Restaurant Booking"),
        ("spa", "Spa Booking"),
        ("birthday", "Birthday Booking"),
        ("concert", "Concert Tickets Booking"),
        ("hotel", "Hotel Reservation"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="bookings")
    booking_type = models.CharField(max_length=20, choices=BOOKING_TYPES)
    location = models.CharField(max_length=200, blank=True, null=True)
    booking_datetime = models.DateTimeField()  # main date/time of booking
    booking_end_date = models.DateTimeField(blank=True, null=True)  # main date/time of booking
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.get_booking_type_display()} @ {self.booking_datetime}"
