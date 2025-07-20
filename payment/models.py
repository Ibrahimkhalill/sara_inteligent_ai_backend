from django.db import models
from django.conf import settings
from authentications.models import UserProfile

# Subscription Plan Model
class SubscriptionPlan(models.Model):
    PLAN_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    name = models.CharField(max_length=50, unique=True)  # Name of the plan (e.g., "Free", "Premium")
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Price of the plan
    duration_type = models.CharField(max_length=10, choices=PLAN_CHOICES, default='monthly')  # Monthly or Yearly subscription
    price_id = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.duration_type.capitalize()}"

# Description Model
class Description(models.Model):
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name="descriptions", null=True, blank=True)  # ForeignKey to SubscriptionPlan
    text = models.CharField(max_length=500,)  # The actual description text
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text[:50]  # Return a preview of the description text

# Subscription Model
class Subscription(models.Model):
    STATUS_CHOICES = [
        ('free', 'Free'),
        ('premium', 'Premium'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name='subscriptions', blank=True, null=True)  # Link to SubscriptionPlan model
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)  # Stripe subscription ID
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='free')  # Free or Premium status
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    duration_days = models.PositiveIntegerField(default=30)  # default 1 month
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if not self.end_date:
            # Determine the end date based on the subscription duration type
            if self.plan and self.plan.duration_type == 'monthly':
                self.end_date = timezone.now() + timezone.timedelta(days=30)
            elif self.plan and self.plan.duration_type == 'yearly':
                self.end_date = timezone.now() + timezone.timedelta(days=365)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} -  ({self.status.capitalize()})"
