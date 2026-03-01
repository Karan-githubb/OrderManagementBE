from django.contrib.auth.models import AbstractUser
from django.db import models
from pharmacies.models import Pharmacy

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('pharmacy', 'Pharmacy'),
    )
    email = models.EmailField(blank=True, default='')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='pharmacy')
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    def __str__(self):
        return f"{self.username} ({self.role})"
