from django.db import models
from datetime import timedelta, datetime
from django.conf import settings
import uuid


class Event(models.Model):
    PRIVACY_CHOICES = [
        ('public', 'Public with Code'),
        ('private', 'Invitation Only'),
        ('hidden', 'Hidden (Organizer Only)'),
    ]

    THEME_CHOICES = [
        ('emerald', 'Emerald'),
        ('gold', 'Gold'),
        ('purple', 'Purple'),
        ('blue', 'Blue'),
        ('coral', 'Coral'),
        ('custom', 'Custom'),
    ]

    # Basic Details
    event_name = models.CharField(max_length=260)
    description = models.TextField(blank=True)

    # Date & Time
    event_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    event_time = models.TimeField(blank=True, null=True)

    # Location
    location = models.CharField(max_length=255, blank=True)

    # Privacy & Settings
    privacy = models.CharField(max_length=10, choices=PRIVACY_CHOICES, default='public')
    allow_upload = models.BooleanField(default=True)
    allow_download = models.BooleanField(default=True)
    allow_tag = models.BooleanField(default=False)
    allow_comment = models.BooleanField(default=False)

    # Appearance
    cover_photo = models.ImageField(upload_to='event_covers/', blank=True, null=True)
    theme_color = models.CharField(max_length=20, choices=THEME_CHOICES, default='emerald')
    custom_theme_color = models.CharField(max_length=20, blank=True, null=True)

    # Code & Ownership
    event_code = models.CharField(max_length=20, unique=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='events')

    # NEW system: Many-to-Many through EventMember
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='EventMember',
        related_name='events_joined',
        blank=True
    )

    # Tracking & Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if isinstance(self.event_date, str):
            self.event_date = datetime.strptime(self.event_date, "%Y-%m-%d").date()

        if not self.end_date:
            self.end_date = self.event_date + timedelta(days=30)

        if not self.event_code:
            while True:
                candidate = uuid.uuid4().hex[:8].upper()
                if not Event.objects.filter(event_code=candidate).exists():
                    self.event_code = candidate
                    break

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.event_name} ({self.event_code})"


# OLD Guest model (temporarily restored for migration)
class Guest(models.Model):
    event = models.ForeignKey(Event, related_name="guests", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.event.event_code})"


# OLD Photo.guest + NEW Photo.uploaded_by co-exist temporarily
class Photo(models.Model):
    event = models.ForeignKey(Event, related_name="photos", on_delete=models.CASCADE)

    # Old reference
    guest = models.ForeignKey(
        Guest, related_name="photos",
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    # New reference
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="uploaded_photos",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    image = models.ImageField(upload_to="event_photos/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo for {self.event.event_name} ({self.event.event_code})"


# NEW EventMember model stays unchanged
class EventMember(models.Model):
    JOIN_METHODS = [
        ('qr', 'QR Code'),
        ('code', 'Event Code'),
        ('invite', 'Invitation'),
        ('face', 'Facial Recognition'),
    ]

    ROLE_CHOICES = [
        ('host', 'Host'),
        ('cohost', 'Co-Host'),
        ('guest', 'Guest'),
        ('photographer', 'Photographer'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='event_memberships')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='memberships')
    joined_at = models.DateTimeField(auto_now_add=True)
    join_method = models.CharField(max_length=20, choices=JOIN_METHODS, default='code')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='guest')
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'event')
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user.username} → {self.event.event_name}"

