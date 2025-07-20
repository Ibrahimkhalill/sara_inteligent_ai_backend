from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import MilkHistory
from .serializers import MilkHistorySerializer
from milkmix.utils import error_response
from django.contrib.auth import get_user_model
User = get_user_model()
# Custom permission for role-based access
from rest_framework.permissions import BasePermission

# class IsFarmUser(BasePermission):
#     def has_permission(self, request, view):
#         return request.user.is_authenticated and request.user.role == 'farm_user'

# class IsConsultantOrAdmin(BasePermission):
#     def has_permission(self, request, view):
#         return request.user.is_authenticated and request.user.role in ['consultant', 'admin']

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_milk_history(request):
    serializer = MilkHistorySerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response({
            "message": "Milk history record created successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)
    return error_response(code=400, details=serializer.errors)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_milk_history(request):
    # Farm users see only their records; consultants/admins see all
    if request.user.role == 'farm_user':
        milk_histories = MilkHistory.objects.filter(user=request.user)
    else:  # consultant or admin
        milk_histories = MilkHistory.objects.all()
    serializer = MilkHistorySerializer(milk_histories, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def milk_history_detail(request, pk):
    try:
        milk_history = MilkHistory.objects.get(pk=pk)
    except MilkHistory.DoesNotExist:
        return error_response(code=404, details={"error": ["Milk history record not found"]})

    # Only farm users can edit/delete their own records
    if request.method in ['PUT', 'DELETE'] and (request.user.role != 'farm_user' or milk_history.user != request.user):
        return error_response(code=403, details={"error": ["You do not have permission to modify this record"]})

    if request.method == 'GET':
        serializer = MilkHistorySerializer(milk_history)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'PUT':
        serializer = MilkHistorySerializer(milk_history, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Milk history record updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return error_response(code=400, details=serializer.errors)

    if request.method == 'DELETE':
        milk_history.delete()
        return Response({"message": "Milk history record deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
    
    


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_milk_history_by_user(request, user_id):
    try:
        target_user = User.objects.get(id=user_id)
        if target_user.role != 'farm_user':
            return error_response(
                code=400,
                details={"error": ["Can only view milk history for farm users"]}
            )
        milk_histories = MilkHistory.objects.filter(user=target_user).order_by('-created_at')
        serializer = MilkHistorySerializer(milk_histories, many=True)
        return Response({
            "message": f"Milk history records for user {target_user.email}",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return error_response(
            code=404,
            details={"error": ["User not found"]}
        )