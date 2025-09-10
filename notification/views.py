from django.shortcuts import render

# Create your views here.
# notifications/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import FCMToken

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_fcm_token(request):
    token = request.data.get("fcm_token")
    if not token:
        return Response({"error": "Token is required"}, status=400)
    
    # Create or ignore if already exists
    obj, created = FCMToken.objects.get_or_create(user=request.user, token=token)
    return Response({"success": True, "created": created})
