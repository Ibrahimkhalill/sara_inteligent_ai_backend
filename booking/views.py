# bookings/views.py
from rest_framework.decorators import api_view , permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from .models import Booking
from .serializers import BookingSerializer
from notification.models import Notification
from datetime import timedelta

NUM_REMINDERS = 3  # number of reminders
REMINDER_INTERVAL = timedelta(hours=5)  # interval between reminders
FIRST_REMINDER_BEFORE = timedelta(days=1)  # start 1 day before


def schedule_reminders(booking):
    """(Re)create the pending reminders for a booking."""
    booking.reminders.filter(sent=False).delete()

    notify_time = booking.booking_datetime - FIRST_REMINDER_BEFORE
    now = timezone.now()
    for _ in range(NUM_REMINDERS):
        # Skip reminders that are already in the past or after the booking time
        if now < notify_time < booking.booking_datetime:
            Notification.objects.create(
                user=booking.user,
                booking=booking,
                message=f"Reminder: Your {booking.get_booking_type_display()} booking is coming up at {booking.booking_datetime.date()}.",
                notify_at=notify_time,
                sent=False
            )
        notify_time += REMINDER_INTERVAL


# List the user's bookings or create a new one
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def booking_list_create(request):
    if request.method == 'GET':
        # Show only the logged-in user's bookings (better security)
        bookings = Booking.objects.filter(user=request.user).order_by("booking_datetime")
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)

    serializer = BookingSerializer(data=request.data)
    if serializer.is_valid():
        # ✅ Save booking with the current user
        booking = serializer.save(user=request.user)
        schedule_reminders(booking)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Retrieve, update, or delete a booking
@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def booking_detail(request, pk):
    try:
        # Users can only access their own bookings
        booking = Booking.objects.get(pk=pk, user=request.user)
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = BookingSerializer(booking)
        return Response(serializer.data)

    if request.method in ('PUT', 'PATCH'):
        serializer = BookingSerializer(booking, data=request.data, partial=request.method == 'PATCH')
        if serializer.is_valid():
            booking = serializer.save()
            schedule_reminders(booking)  # the date may have changed
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    booking.delete()  # pending reminders are deleted with it
    return Response(status=status.HTTP_204_NO_CONTENT)
