# events/admin.py
from django.contrib import admin
from django import forms
import os
from .models import Event, EventMember, FaceIndexJob, Photo, UploadJob
from .image_validation import safe_image_filename, validate_image_upload


class EventAdminForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = "__all__"

    def clean_cover_photo(self):
        image = self.cleaned_data.get("cover_photo")
        if image and not getattr(image, "_committed", False):
            _, extension = validate_image_upload(image)
            image.name = safe_image_filename(image.name, extension)
        return image


# -----------------------------------------
# Inline for Members inside Event admin
# -----------------------------------------
class EventMemberInline(admin.TabularInline):
    model = EventMember
    extra = 0
    autocomplete_fields = ["user"]
    fields = (
        "user", "role", "join_method", "is_active", "can_upload", "photo_limit_override",
        "joined_at", "face_consent_at", "face_model_version",
    )
    readonly_fields = ["joined_at", "face_consent_at", "face_model_version"]


# -----------------------------------------
# Inline Photos for Event admin
# -----------------------------------------
class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 0
    fields = ("uploaded_by", "private_filename", "uploaded_at")
    readonly_fields = ("uploaded_by", "private_filename", "uploaded_at")

    @admin.display(description="Photo file")
    def private_filename(self, obj):
        return os.path.basename(obj.image.name) if obj.image else "Unavailable"


# -----------------------------------------
# Event Admin
# -----------------------------------------
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    form = EventAdminForm
    list_display = ("event_name", "event_code", "event_date", "created_by", "privacy", "is_active", "max_photo_count")
    list_filter = ("privacy", "theme_color", "is_active")
    search_fields = ("event_name", "event_code", "created_by__username")
    inlines = [EventMemberInline, PhotoInline]
    readonly_fields = ("event_code", "created_at", "updated_at")


# -----------------------------------------
# Event Member Admin
# -----------------------------------------
@admin.register(EventMember)
class EventMemberAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "role", "join_method", "can_upload", "photo_limit_override", "face_enrolled", "joined_at", "is_active")
    list_filter = ("role", "join_method", "is_active")
    search_fields = ("user__username", "event__event_name")
    fields = (
        "user", "event", "joined_at", "join_method", "role", "is_active", "can_upload",
        "photo_limit_override", "face_enrolled", "face_consent_at", "face_model_version",
    )
    readonly_fields = ("joined_at", "face_enrolled", "face_consent_at", "face_model_version")

    @admin.display(boolean=True, description="Face matching opted in")
    def face_enrolled(self, obj):
        return bool(obj.face_consent_at and obj.face_embedding_ciphertext)


# -----------------------------------------
# Photo Admin
# -----------------------------------------
@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("event", "uploaded_by", "uploaded_at")
    list_filter = ("uploaded_at",)
    search_fields = ("event__event_name", "uploaded_by__username")
    fields = ("event", "uploaded_by", "private_filename", "uploaded_at")
    readonly_fields = fields

    @admin.display(description="Photo file")
    def private_filename(self, obj):
        return os.path.basename(obj.image.name) if obj.image else "Unavailable"

    def has_add_permission(self, request):
        return False


@admin.register(UploadJob)
class UploadJobAdmin(admin.ModelAdmin):
    list_display = ("original_name", "event", "uploader", "status", "priority", "attempts", "created_at")
    list_filter = ("status", "priority", "created_at")
    search_fields = ("original_name", "event__event_name", "uploader__username", "error_message")
    fields = (
        "event", "uploader", "original_name", "staged_filename", "idempotency_key",
        "status", "priority", "attempts", "max_attempts", "available_at",
        "error_message", "photo", "created_at", "updated_at", "finished_at",
    )
    readonly_fields = fields
    ordering = ("-priority", "created_at")

    @admin.display(description="Staged file")
    def staged_filename(self, obj):
        return obj.source_file.name or "Removed after processing"

    def has_add_permission(self, request):
        return False


@admin.register(FaceIndexJob)
class FaceIndexJobAdmin(admin.ModelAdmin):
    list_display = ("photo", "status", "attempts", "available_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("photo__event__event_name", "error_message")
    readonly_fields = tuple(field.name for field in FaceIndexJob._meta.fields)

    def has_add_permission(self, request):
        return False
