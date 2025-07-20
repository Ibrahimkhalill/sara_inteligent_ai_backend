from django.urls import path
from . import views

urlpatterns = [
    path('members/create/', views.create_member, name='create_member'),
    path('members/farm/<int:farm_id>/', views.list_farm_members, name='list_farm_members'),
   
]