from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from .serializers import  FarmSerializer, ConsultantRequestSerializer
from .models import  ConsultantFarm, ConsultantRequest
from Member.serializers import MemberSerializer
from Member.models import Member
from milkmix.utils import error_response
from django.db.models import Q

from django.db import transaction

User = get_user_model()




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_farms(request):
    name = request.query_params.get('name', '')
    farms = User.objects.filter(
        role='farm',
        user_profile__name__icontains=name
    ).select_related('user_profile')[:10]  # Limit to 10 results
    serializer = FarmSerializer(farms, many=True)
    return Response({
        "message": "Farms retrieved successfully",
        "data": serializer.data
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_consultant_request(request):
    serializer = ConsultantRequestSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        consultant = serializer.validated_data['consultant']
        if request.user != consultant and request.user.role != 'admin':
            return error_response(
                code=403,
                details={"error": ["You are not authorized to send requests as this consultant"]}
            )
        request_obj = serializer.save()
        return Response({
            "message": "Consultant request sent successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)
    return error_response(code=400, details=serializer.errors)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manage_consultant_request(request, pk):
    try:
        consultant_request = ConsultantRequest.objects.get(pk=pk, status='pending')
        if request.user != consultant_request.farm and request.user.role != 'admin':
            return error_response(
                code=403,
                details={"error": ["You are not authorized to manage this request"]}
            )
        action = request.data.get('action')
        if action not in ['accept', 'decline']:
            return error_response(
                code=400,
                details={"error": ["Invalid action. Must be 'accept' or 'decline'"]}
            )
        with transaction.atomic():
            if action == 'accept':
                consultant_request.status = 'accepted'
                ConsultantFarm.objects.create(
                    farm=consultant_request.farm,
                    consultant=consultant_request.consultant
                )
            else:
                consultant_request.status = 'declined'
            consultant_request.save()
        serializer = ConsultantRequestSerializer(consultant_request)
        return Response({
            "message": f"Consultant request {action}ed successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    except ConsultantRequest.DoesNotExist:
        return error_response(
            code=404,
            details={"error": ["Consultant request not found or already processed"]}
        )
        
        
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_pending_requests(request):
    if request.user.role not in ['farm', 'admin']:
        return error_response(
            code=403,
            details={"error": ["Only farms or admins can view pending requests"]}
        )
    requests = ConsultantRequest.objects.filter(
        farm=request.user,
        status='pending'
    ).select_related('farm', 'consultant', 'farm__user_profile', 'consultant__user_profile')
    serializer = ConsultantRequestSerializer(requests, many=True)
    return Response({
        "message": "Pending consultant requests retrieved successfully",
        "data": serializer.data
    }, status=status.HTTP_200_OK)
    
    
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_accepted_requests(request):
    if request.user.role not in ['consultant', 'admin' ,'farm']:
        return error_response(
            code=403,
            details={"error": ["Only consultants or admins can view pending requests"]}
        )
    requests = ConsultantRequest.objects.filter(
        consultant=request.user,
        status='accepted'
    ).select_related('farm', 'consultant', 'farm__user_profile', 'consultant__user_profile')
    serializer = ConsultantRequestSerializer(requests, many=True)
    return Response({
        "message": "Accepted Farm List retrieved successfully",
        "data": serializer.data
    }, status=status.HTTP_200_OK)   
    
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_farm_members(request, farm_id):
    try:
        farm = User.objects.get(id=farm_id, role='farm')
        members = Member.objects.filter(farm=farm, is_active=True)
        serializer = MemberSerializer(members, many=True)
        return Response({
            "message": f"Members of farm {farm.email}",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return error_response(
            code=404,
            details={"error": ["Farm not found or not a farm role"]}
        )
        