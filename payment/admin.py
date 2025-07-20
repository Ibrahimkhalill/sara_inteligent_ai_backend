from django.contrib import admin
from .models import Subscription, SubscriptionPlan, Description

# Inline admin for Description (to be displayed directly in SubscriptionPlan admin)
class DescriptionInline(admin.TabularInline):
    model = Description  # Linking the Description model
    extra = 1  # One empty form to add new descriptions

# SubscriptionPlan Admin
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('price_id','name', 'amount', 'duration_type', 'created_at', 'updated_at')
    search_fields = ('name',)
    list_filter = ('duration_type',)
    inlines = [DescriptionInline]  # This will allow adding descriptions in the SubscriptionPlan admin

# Subscription Admin
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'start_date', 'end_date', 'is_active')
    search_fields = ('user__email', 'plan__name')  # Searching by user email and plan name
    list_filter = ('status', 'is_active')
    readonly_fields = ('start_date', 'end_date')

# Description Admin
class DescriptionAdmin(admin.ModelAdmin):
    list_display = ('plan', 'text', 'created_at')  # Plan and Description text
    search_fields = ('text',)  # Searching by description text

# Registering the models with the custom admin views
admin.site.register(Subscription, SubscriptionAdmin)
admin.site.register(SubscriptionPlan, SubscriptionPlanAdmin)
admin.site.register(Description, DescriptionAdmin)
