# bookings/views.py
from rest_framework.decorators import api_view , permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Booking
from .serializers import BookingSerializer
from notification.models import Notification
# List all bookings or create a new one
from datetime import timedelta


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def booking_list_create(request):
    if request.method == 'GET':
        # Show only the logged-in user's bookings (better security)
        bookings = Booking.objects.filter(user=request.user).order_by("booking_datetime")
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = BookingSerializer(data=request.data)
        if serializer.is_valid():
            # ✅ Save booking with the current user
            booking = serializer.save(user=request.user)

            # --- Create multiple reminders ---
            num_reminders = 3  # number of reminders
            interval = timedelta(hours=5)  # interval between reminders
            notify_time = booking.booking_datetime - timedelta(days=1)  # start 1 day before

            for i in range(num_reminders):
                # Prevent reminder from being scheduled after the booking time
                if notify_time < booking.booking_datetime:
                    Notification.objects.create(
                        user=booking.user,
                        message=f"Reminder: Your {booking.get_booking_type_display()} booking is coming up at {booking.booking_datetime.date()}.",
                        notify_at=notify_time,
                        sent=False
                    )
                notify_time += interval  # next reminder after interval

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
# Retrieve, update, or delete a booking


@api_view(['GET', 'PUT', 'DELETE'])
def booking_detail(request, pk):
    try:
        booking = Booking.objects.get(pk=pk)
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = BookingSerializer(booking)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = BookingSerializer(booking, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        booking.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
