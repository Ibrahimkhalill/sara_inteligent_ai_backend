from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class ConsultantFarm(models.Model):
    farm = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consultant_farms')
    consultant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consulted_farms')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('farm', 'consultant')
        verbose_name = 'Consultant Farm'
        verbose_name_plural = 'Consultant Farms'

    def __str__(self):
        return f"{self.consultant.email} consulting for {self.farm.email}"

class ConsultantRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    )
    farm = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consultant_requests_received')
    consultant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consultant_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('farm', 'consultant')
        verbose_name = 'Consultant Request'
        verbose_name_plural = 'Consultant Requests'

    def __str__(self):
        return f"Request: {self.consultant.email} to consult for {self.farm.email} ({self.status})"