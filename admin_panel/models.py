from django.contrib.auth.models import User
from django.db import models
import uuid

class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=150, default="JJ Halal Farms")
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="admin_avatars/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username