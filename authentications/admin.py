from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, UserProfile, OTP


class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'role', 'is_staff', 'is_active')  # Added 'role'
    list_filter = ('role', 'is_staff', 'is_active', 'is_superuser')  # Added 'role' to filters
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'is_staff', 'is_active', 'is_superuser')}),
    )
    search_fields = ('email',)
    ordering = ('email',)
    filter_horizontal = ('groups', 'user_permissions',)

# Inline for managing languages in GuideProfile


# Customize GuideProfile admin

# Register CustomUser
admin.site.register(CustomUser)

# Register other models
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'name','phone_number')
    search_fields = ('user__email', 'name', 'phone_number')

@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'otp', 'created_at', 'attempts')
    list_filter = ('created_at',)
    search_fields = ('email', 'otp')

