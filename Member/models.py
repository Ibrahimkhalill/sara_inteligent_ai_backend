from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Member(models.Model):
    farm = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='farm_members',
        limit_choices_to={'role': 'farm'},
        help_text=_('The farm to which this member belongs')
    )
    farm_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='member_farms',
        limit_choices_to={'role': 'farm_user'},
        help_text=_('The farm user associated with this farm')
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text=_('Timestamp when the member was added'))
    is_active = models.BooleanField(default=True, help_text=_('Whether the member is active in the farm'))

    class Meta:
        verbose_name = _('Member')
        verbose_name_plural = _('Members')
        unique_together = ('farm', 'farm_user')  # Prevent duplicate farm-farm_user pairs
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.farm_user.email} (Member of {self.farm.email})"

    def save(self, *args, **kwargs):
        # Validate roles before saving
        if self.farm.role != 'farm':
            raise ValueError("Farm must have role 'farm'")
        if self.farm_user.role != 'farm_user':
            raise ValueError("Farm user must have role 'farm_user'")
        super().save(*args, **kwargs)