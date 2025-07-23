from django.urls import path
from . import views

urlpatterns = [
   
    path('consultants/search/farm/', views.search_farms, name='search_farms'),
    path('consultants/request/', views.send_consultant_request, name='send_consultant_request'),
    path('consultants/request/<int:pk>/manage/', views.manage_consultant_request, name='manage_consultant_request'),
    path('consultants/request-list/', views.list_pending_requests, name='manage_consultant_request'),
    path('consultants/farm/list/', views.list_accepted_requests, name='manage_consultant_request'),
    path('consultants/farm/<int:farm_id>/memnber-list/', views.list_farm_members, name='manage_consultant_request'),
]