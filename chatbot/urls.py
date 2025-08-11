# subscriptions/urls.py

from django.urls import path
from . import views

urlpatterns = [

    path("ai-chat/", views.chatbot_response),

]
