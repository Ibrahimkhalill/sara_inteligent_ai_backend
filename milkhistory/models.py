from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from Member.models import Member

class MilkHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='milk_histories',
        help_text=_('The user who created this milk preparation record (farm or farm_user)')
    )
    farm = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=True, null=True,
        related_name='farm_milk_histories',
        limit_choices_to={'role': 'farm'},
        help_text=_('The farm associated with this milk preparation record')
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text=_('Timestamp when the record was created'))
    bottle_size = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text=_('Size of each bottle in liters or specified unit')
    )
    number_of_bottles = models.PositiveIntegerField(
        default=1, help_text=_('Number of bottles prepared')
    )
    hospital_solids = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text=_('Percentage or weight of solids in hospital milk')
    )
    hospital_milk_volume = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text=_('Volume of hospital milk used in liters or specified unit')
    )
    desired_solids_content = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text=_('Desired solids content percentage for the milk mixture')
    )
    pounds_of_water = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text=_('Pounds of water used in the mixture')
    )
    pounds_of_milk_replacer = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text=_('Pounds of milk replacer used in the mixture')
    )
    solids_hospital_milk = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text=_('Weight of solids contributed by hospital milk')
    )
    hospital_milk_used = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text=_('Amount of hospital milk used in pounds or specified unit')
    )
    total_volume = models.CharField(
        max_length=400, null=True, blank=True,
        help_text=_('Total volume of the milk mixture prepared')
    )

    class Meta:
        verbose_name = _('Milk History')
        verbose_name_plural = _('Milk Histories')
        ordering = ['-created_at']

    # def __str__(self):
    #     return f"Milk History for {self.user.email} on {self.created_at.strftime('%Y-%m-%d %H:%M:%S')} (Farm: {self.farm.email})"

    def save(self, *args, **kwargs):
        # Validate user role
        if self.user.role not in ['farm', 'farm_user']:
            raise ValueError("User must have role 'farm' or 'farm_user'")
        # Validate farm role
        if self.farm.role != 'farm':
            raise ValueError("Farm must have role 'farm'")
        # For farm_user, ensure they are an active member of the farm
        if self.user.role == 'farm_user' and not Member.objects.filter(farm=self.farm, farm_user=self.user, is_active=True).exists():
            raise ValueError("User is not an active member of this farm")
        # For farm, ensure farm field matches the user
        if self.user.role == 'farm' and self.farm != self.user:
            raise ValueError("Farm user must set farm field to themselves")
        super().save(*args, **kwargs)