# subscriptions/urls.py

from django.urls import path
from . import views

urlpatterns = [
  
    path("list/", views.booking_list_create),
    path("create/", views.booking_list_create),

]
