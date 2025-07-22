from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Member
from .serializers import MemberSerializer
from milkmix.utils import error_response
from authentications.models import CustomUser

@api_view(['POST'])
@permission_classes([IsAuthenticated])  # Restrict to admins if needed
def create_member(request):
    serializer = MemberSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        member = serializer.save()
        return Response({
            "message": "Member added to farm successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)
    return error_response(code=400, details=serializer.errors)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_farm_members(request, farm_id):
    try:
        farm = CustomUser.objects.get(id=farm_id, role='farm')
        members = Member.objects.filter(farm=farm, is_active=True)
        serializer = MemberSerializer(members, many=True)
        return Response({
            "message": f"Members of farm {farm.email}",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    except CustomUser.DoesNotExist:
        return error_response(
            code=404,
            details={"error": ["Farm not found or not a farm role"]}
        )
        
        
        
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_farm_user_details(request):
    try:
        
        user = request.user
    
        if user.role != 'farm_user':
            return error_response(
                code=403,
                details={"error": ["User is not a farm user"]}
            )
        member = Member.objects.get(farm_user=user, is_active=True)
        serializer = MemberSerializer(member)
        return Response({
            "message": "Farm user details retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    except CustomUser.DoesNotExist:
        return error_response(
            code=404,
            details={"error": ["User not found or not a farm user"]})