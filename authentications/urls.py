from django.urls import path
from . import views

urlpatterns = [
    path('sign-up/', views.register_user),
    path('sign-in/', views.login),
    path('google-login/', views.google_login),
    path('users/', views.list_users),
    path('profile/', views.user_profile),
    path('otp/create/', views.create_otp),
    path('otp/verify/', views.verify_otp),
    path('password-reset-otp/', views.request_password_reset),
    path('password-reset/confirm/', views.reset_password),
    path('password-change/', views.change_password),
    path('reset/otp-verify/', views.verify_otp_reset),
    path('refresh/', views.get_access_token_by_refresh_token),
]
