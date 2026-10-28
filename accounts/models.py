
# Create your models here.

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from events.storage import PrivatePhotoStorage


# accounts/models.py
from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # extra info
    bio = models.TextField(blank=True, null=True)
    profile_pic = models.ImageField(storage=PrivatePhotoStorage(), upload_to='profile_pics/', blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)

    # privacy & settings
    profile_visibility = models.CharField(
        max_length=20,
        choices=[("public", "Public"), ("friends", "Friends Only"), ("private", "Private")],
        default="friends",
    )
    email_notifications = models.BooleanField(default=True)
    auto_share_photos = models.BooleanField(default=False)
    allow_event_invites = models.CharField(
        max_length=20,
        choices=[("anyone", "Anyone"), ("friends", "Friends Only"), ("none", "No One")],
        default="anyone",
    )

    def __str__(self):
        return f"{self.user.username} ({self.user.email})"

# 👇 signal: auto create/update profile
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)  # naya profile banao
 # update ke time bhi save ho


from events.models import Event  # so activities can link to events
from django.conf import settings

class Activity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activities"
    )
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, blank=True, null=True, related_name="activities"
    )
    title = models.CharField(max_length=255)   # short title
    description = models.TextField(blank=True) # extra details if needed
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.title}"
