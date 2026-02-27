from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = [
        ('manager', 'Manager'),
        ('staff', 'Staff'),
        ('stock', 'Stock'),
    ]
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    mobile_number = models.CharField(max_length=15, blank=True, null=True)
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
