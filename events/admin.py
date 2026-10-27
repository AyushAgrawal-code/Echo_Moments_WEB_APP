# events/admin.py
from django.contrib import admin
from .models import Event, EventMember, Photo


# -----------------------------------------
# Inline for Members inside Event admin
# -----------------------------------------
class EventMemberInline(admin.TabularInline):
    model = EventMember
    extra = 0
    autocomplete_fields = ["user"]
    readonly_fields = ["joined_at"]


# -----------------------------------------
# Inline Photos for Event admin
# -----------------------------------------
class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 0
    readonly_fields = ["uploaded_at"]


# -----------------------------------------
# Event Admin
# -----------------------------------------
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("event_name", "event_code", "event_date", "created_by", "privacy", "is_active")
    list_filter = ("privacy", "theme_color", "is_active")
    search_fields = ("event_name", "event_code", "created_by__username")
    inlines = [EventMemberInline, PhotoInline]
    readonly_fields = ("event_code", "created_at", "updated_at")


# -----------------------------------------
# Event Member Admin
# -----------------------------------------
@admin.register(EventMember)
class EventMemberAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "role", "join_method", "joined_at", "is_active")
    list_filter = ("role", "join_method", "is_active")
    search_fields = ("user__username", "event__event_name")


# -----------------------------------------
# Photo Admin
# -----------------------------------------
@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("event", "uploaded_by", "uploaded_at")
    list_filter = ("uploaded_at",)
    search_fields = ("event__event_name", "uploaded_by__username")
