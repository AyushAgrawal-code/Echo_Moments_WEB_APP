from django.db import models
from datetime import timedelta, datetime
from django.conf import settings
from django.core.exceptions import ValidationError
import uuid

from .storage import PrivatePhotoStorage, PrivateUploadStorage


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

    # Photo capacity is independent from membership/view access. A blank limit
    # means that particular cap is not configured; max_photo_count remains the
    # event-wide hard stop when it is set.
    max_photo_count = models.PositiveIntegerField(blank=True, null=True)
    host_photo_limit = models.PositiveIntegerField(blank=True, null=True)
    guest_photo_pool_limit = models.PositiveIntegerField(blank=True, null=True)
    member_photo_limit_enabled = models.BooleanField(default=False)
    default_member_photo_limit = models.PositiveIntegerField(blank=True, null=True)

    # Appearance
    cover_photo = models.ImageField(storage=PrivatePhotoStorage(), upload_to='event_covers/', blank=True, null=True)
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

    def clean(self):
        super().clean()
        if (
            self.max_photo_count is not None
            and self.host_photo_limit is not None
            and self.guest_photo_pool_limit is not None
            and self.host_photo_limit + self.guest_photo_pool_limit > self.max_photo_count
        ):
            raise ValidationError({
                "guest_photo_pool_limit": "Host and guest allocations cannot exceed the event photo cap."
            })

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

    image = models.ImageField(storage=PrivatePhotoStorage(), upload_to="event_photos/")
    analysis_image = models.ImageField(
        storage=PrivatePhotoStorage(), upload_to="event_analysis/", blank=True
    )
    face_embeddings_ciphertext = models.TextField(blank=True)
    face_embedding_model_version = models.CharField(max_length=80, blank=True)
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
    can_upload = models.BooleanField(default=True)
    photo_limit_override = models.PositiveIntegerField(blank=True, null=True)

    # Face matching is opt-in per event. Only the encrypted feature vector is
    # retained; the enrollment selfie is processed in memory and discarded.
    face_embedding_ciphertext = models.TextField(blank=True)
    face_consent_at = models.DateTimeField(blank=True, null=True)
    face_model_version = models.CharField(max_length=40, blank=True)

    class Meta:
        unique_together = ('user', 'event')
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user.username} → {self.event.event_name}"


class UploadJob(models.Model):
    """Durable per-photo upload queue entry.

    The browser sends each file separately. The saved queue item survives page
    reloads and lets a worker process host uploads ahead of guest uploads.
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="upload_jobs")
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_upload_jobs"
    )
    source_file = models.FileField(storage=PrivateUploadStorage(), upload_to="upload_queue/%Y/%m/%d/", blank=True)
    original_name = models.CharField(max_length=255)
    idempotency_key = models.UUIDField(default=uuid.uuid4)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    priority = models.PositiveSmallIntegerField(default=0)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    claim_token = models.UUIDField(blank=True, null=True, editable=False)
    available_at = models.DateTimeField()
    error_message = models.CharField(max_length=500, blank=True)
    photo = models.OneToOneField(
        Photo, on_delete=models.SET_NULL, null=True, blank=True, related_name="upload_job"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-priority", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "uploader", "idempotency_key"],
                name="uniq_upload_idempotency_per_member_event",
            )
        ]
        indexes = [
            models.Index(fields=["status", "priority", "available_at"]),
            models.Index(fields=["event", "uploader", "status"]),
        ]

    def __str__(self):
        return f"{self.original_name} ({self.status})"


class FaceIndexJob(models.Model):
    """Retryable background work that finds enrolled members in one photo."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    photo = models.OneToOneField(Photo, on_delete=models.CASCADE, related_name="face_index_job")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    generation = models.PositiveIntegerField(default=1)
    available_at = models.DateTimeField()
    error_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["status", "available_at"])]

    def __str__(self):
        return f"Face indexing for photo {self.photo_id} ({self.status})"


class FaceMatch(models.Model):
    """Private, user-specific suggestion that an event photo contains them."""

    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name="face_matches")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="face_matches")
    similarity = models.FloatField()
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["photo", "user"], name="uniq_face_match_photo_user")]
        indexes = [models.Index(fields=["user", "is_hidden", "created_at"])]

    def __str__(self):
        return f"Face suggestion for user {self.user_id}, photo {self.photo_id}"

