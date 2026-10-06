from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentications.models import CustomUser
from notification.models import Notification
from .models import Booking


class BookingTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(email="b@test.com", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def create(self, starts_in, **extra):
        start = timezone.now() + starts_in
        return self.client.post(
            "/api/booking/create/",
            {"booking_type": "spa", "booking_datetime": start.isoformat(), **extra},
            format="json",
        )

    def test_reminders_are_scheduled_only_in_the_future(self):
        self.create(timedelta(hours=2))
        self.assertEqual(Notification.objects.count(), 0)
        self.create(timedelta(days=3))
        self.assertEqual(Notification.objects.count(), 3)

    def test_end_before_start_is_rejected(self):
        response = self.create(
            timedelta(days=3), booking_end_date=(timezone.now() + timedelta(days=2)).isoformat()
        )
        self.assertEqual(response.status_code, 400)

    def test_users_only_see_their_own_bookings(self):
        booking_id = self.create(timedelta(days=3)).data["id"]
        self.assertEqual(self.client.get(f"/api/booking/{booking_id}/").status_code, 200)

        other = APIClient()
        other.force_authenticate(CustomUser.objects.create_user(email="o@test.com", password="x"))
        self.assertEqual(other.get(f"/api/booking/{booking_id}/").status_code, 404)
        self.assertEqual(other.delete(f"/api/booking/{booking_id}/").status_code, 404)

    def test_editing_the_date_reschedules_reminders(self):
        booking_id = self.create(timedelta(days=3)).data["id"]
        new_start = timezone.now() + timedelta(days=10)
        response = self.client.put(
            f"/api/booking/{booking_id}/",
            {"booking_type": "hotel", "location": "Dhaka", "booking_datetime": new_start.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        reminders = Notification.objects.filter(booking_id=booking_id).order_by("notify_at")
        self.assertEqual(reminders.count(), 3)
        self.assertAlmostEqual(
            reminders[0].notify_at.timestamp(), (new_start - timedelta(days=1)).timestamp(), delta=1
        )

    def test_delete_removes_booking_and_reminders(self):
        booking_id = self.create(timedelta(days=3)).data["id"]
        self.assertEqual(self.client.delete(f"/api/booking/{booking_id}/").status_code, 204)
        self.assertFalse(Booking.objects.filter(id=booking_id).exists())
        self.assertEqual(Notification.objects.count(), 0)
