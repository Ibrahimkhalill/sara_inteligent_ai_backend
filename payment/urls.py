# subscriptions/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path("create-checkout-session/", views.create_checkout_session, name="create_checkout_session"),
    path("webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("success/", views.checkout_success, name="checkout_success"),
    path("cancel/", views.checkout_cencel, name="checkout_cancel"),
    path("me/", views.get_subscription, name="get_subscription"),

]
