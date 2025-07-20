from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.conf import settings

class CustomUserManager(BaseUserManager):
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email field is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        return self._create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLES = (
        ('admin', 'Admin'),
        ('farm', 'Farm'),
        ('consultant', 'Consultant'),
        ('farm_user', 'Farm User'),
    )
    email = models.EmailField(_('email address'), unique=True)
    role = models.CharField(max_length=10, choices=ROLES, default='farm')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} ({self.role})"

class OTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.IntegerField(default=0)

    def __str__(self):
        return f'OTP for {self.email}: {self.otp}'

    def save(self, *args, **kwargs):
        with transaction.atomic():
            OTP.objects.filter(email=self.email).delete()
            super().save(*args, **kwargs)

    def is_expired(self):
        from django.utils import timezone
        return (timezone.now() - self.created_at).seconds > 120

class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='user_profile'
    )
    
    name = models.CharField(max_length=200, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to="profile", blank=True, null=True)
    joined_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    
    def __str__(self):
        return self.user.email if self.user else "No User"