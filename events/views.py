from datetime import datetime
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError
from django.db import transaction
from django.http import JsonResponse, HttpResponse, FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Event, EventMember, Photo

MAX_UPLOAD_SIZE = 10 * 1024 * 1024


def _membership(event, user):
    return EventMember.objects.filter(event=event, user=user, is_active=True).first()


def _is_host(event, user):
    return user.is_authenticated and event.created_by_id == user.id


def _can_view(event, user):
    if not user.is_authenticated:
        return False
    if _is_host(event, user):
        return True
    membership = _membership(event, user)
    if event.privacy == "hidden":
        return False
    if event.privacy == "private":
        return membership is not None
    return membership is not None


@login_required
def scan_qr_page(request):
    return render(request, "events/scan_qr.html")


@login_required
def join_event(request):
    if request.method == "POST":
        code = request.POST.get("event_code", "").strip().upper()
        event = Event.objects.filter(event_code=code).first()
        if not event:
            messages.error(request, "Invalid event code.")
            return redirect("events:join_event")
        if not event.is_active:
            messages.error(request, "This event has ended.")
            return redirect("events:join_event")
        if event.privacy in ("private", "hidden") and not _is_host(event, request.user):
            messages.error(request, "This event requires an invitation.")
            return redirect("events:join_event")
        membership, created = EventMember.objects.get_or_create(
            user=request.user, event=event,
            defaults={"join_method": "code", "role": "guest", "is_active": True},
        )
        if not created and not membership.is_active:
            messages.error(request, "Your membership in this event is inactive.")
            return redirect("events:join_event")
        return redirect("events:event_detail", event_code=event.event_code)
    return render(request, "events/join_event.html")


@login_required
def create_event(request):
    if request.method == "POST":
        name = request.POST.get("event_name", "").strip()
        date_value = request.POST.get("event_date", "").strip()
        if not name or not date_value:
            return JsonResponse({"success": False, "error": "Event name and date are required."}, status=400)
        try:
            event_date = datetime.strptime(date_value, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"success": False, "error": "Enter a valid event date."}, status=400)
        privacy = request.POST.get("privacy", "public")
        theme = request.POST.get("theme_color", "emerald")
        if privacy not in dict(Event.PRIVACY_CHOICES) or theme not in dict(Event.THEME_CHOICES):
            return JsonResponse({"success": False, "error": "Invalid event settings."}, status=400)
        try:
            with transaction.atomic():
                event = Event.objects.create(
                    created_by=request.user, event_name=name, event_date=event_date,
                    event_time=request.POST.get("event_time") or None,
                    location=request.POST.get("location", "").strip(),
                    description=request.POST.get("description", "").strip(),
                    privacy=privacy, theme_color=theme,
                    cover_photo=request.FILES.get("cover_photo"),
                    allow_upload="allow_upload" in request.POST,
                    allow_download="allow_download" in request.POST,
                    allow_tag="allow_tag" in request.POST,
                    allow_comment="allow_comment" in request.POST,
                )
                EventMember.objects.create(user=request.user, event=event, role="host", join_method="code")
        except (ValidationError, ValueError) as exc:
            return JsonResponse({"success": False, "error": str(exc)}, status=400)
        return JsonResponse({"success": True, "event_code": event.event_code, "url": redirect("events:event_detail", event_code=event.event_code).url, "join_url": request.build_absolute_uri(redirect("events:join_event").url) + "?event_code=" + event.event_code}, status=201)
    return render(request, "events/host.html")


@login_required
def event_detail(request, event_code):
    event = get_object_or_404(Event, event_code=event_code)
    if not _can_view(event, request.user):
        if not event.is_active:
            return render(request, "events/event_unavailable.html", {"event": event}, status=410)
        return HttpResponse("You do not have access to this event.", status=403)
    members = event.memberships.filter(is_active=True).select_related("user")
    photos = event.photos.order_by("-uploaded_at")
    context = {"event": event, "members": members, "photos": photos,
               "is_host": _is_host(event, request.user),
               "membership": _membership(event, request.user),
               "stats": {"total_photos": photos.count(), "active_guests": members.count(), "recent_uploads": photos[:3]}}
    return render(request, "events/host_dashboard.html" if context["is_host"] else "events/guest_event.html", context)


@login_required
@require_POST
def toggle_upload_status(request, event_code):
    event = get_object_or_404(Event, event_code=event_code)
    if not _is_host(event, request.user):
        return JsonResponse({"success": False, "error": "Host access required."}, status=403)
    if not event.is_active:
        return JsonResponse({"success": False, "error": "Event has ended."}, status=410)
    event.allow_upload = not event.allow_upload
    event.save(update_fields=["allow_upload", "updated_at"])
    return JsonResponse({"success": True, "new_status": event.allow_upload})


@login_required
@require_POST
def upload_photo(request, event_code):
    event = get_object_or_404(Event, event_code=event_code)
    if not _membership(event, request.user):
        return JsonResponse({"success": False, "error": "Join this event to upload."}, status=403)
    if not event.is_active or not event.allow_upload:
        return JsonResponse({"success": False, "error": "Uploads are not available for this event."}, status=403)
    files = request.FILES.getlist("images") or request.FILES.getlist("image")
    if not files:
        return JsonResponse({"success": False, "error": "Choose at least one image."}, status=400)
    if len(files) > 20:
        return JsonResponse({"success": False, "error": "Upload at most 20 images at a time."}, status=400)
    created = []
    try:
        with transaction.atomic():
            for image in files:
                if image.size > MAX_UPLOAD_SIZE:
                    raise ValueError(f"{image.name} exceeds the 10 MB limit.")
                try:
                    with Image.open(image) as verified_image:
                        if verified_image.format not in ("JPEG", "PNG", "GIF", "WEBP"):
                            raise ValueError(f"{image.name} is not a supported image.")
                        verified_image.verify()
                except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
                    raise ValueError(f"{image.name} is not a valid image.")
                image.seek(0)
                photo = Photo(event=event, uploaded_by=request.user)
                photo.image.save(image.name, image, save=False)
                created.append(photo)
                photo.save()
    except (ValueError, ValidationError) as exc:
        for photo in created:
            if photo.image:
                photo.image.delete(save=False)
        return JsonResponse({"success": False, "error": str(exc)}, status=400)
    except Exception:
        for photo in created:
            if photo.image:
                photo.image.delete(save=False)
        return JsonResponse({"success": False, "error": "The upload could not be saved."}, status=500)
    return JsonResponse({"success": True, "photos": [{"id": p.id, "url": p.image.url, "uploaded_at": p.uploaded_at.isoformat()} for p in created]}, status=201)


@login_required
@require_POST
def remove_member(request, event_code, user_id):
    event = get_object_or_404(Event, event_code=event_code)
    if not _is_host(event, request.user):
        return JsonResponse({"success": False, "error": "Host access required."}, status=403)
    if not event.is_active:
        return JsonResponse({"success": False, "error": "Event has ended."}, status=410)
    membership = get_object_or_404(EventMember, event=event, user_id=user_id, is_active=True)
    if membership.role == "host" or membership.user_id == event.created_by_id:
        return JsonResponse({"success": False, "error": "The host cannot be removed."}, status=400)
    membership.is_active = False
    membership.save(update_fields=["is_active"])
    return JsonResponse({"success": True})


@login_required
@require_POST
def end_event(request, event_code):
    event = get_object_or_404(Event, event_code=event_code)
    if not _is_host(event, request.user):
        return JsonResponse({"success": False, "error": "Host access required."}, status=403)
    event.is_active = False
    event.save(update_fields=["is_active", "updated_at"])
    return JsonResponse({"success": True})


@login_required
@require_POST
def delete_photo(request, event_code, photo_id):
    event = get_object_or_404(Event, event_code=event_code)
    photo = get_object_or_404(Photo, event=event, pk=photo_id)
    if not _membership(event, request.user):
        return JsonResponse({"success": False, "error": "Event membership required."}, status=403)
    if photo.uploaded_by_id != request.user.id and not _is_host(event, request.user):
        return JsonResponse({"success": False, "error": "You can only delete your own uploads."}, status=403)
    image = photo.image
    photo.delete()
    if image:
        image.delete(save=False)
    return JsonResponse({"success": True})


@login_required
def download_photo(request, event_code, photo_id):
    event = get_object_or_404(Event, event_code=event_code)
    if not _can_view(event, request.user):
        return HttpResponse("Event membership required.", status=403)
    if not event.allow_download:
        return HttpResponse("Downloads are disabled for this event.", status=403)
    photo = get_object_or_404(Photo, event=event, pk=photo_id)
    if not photo.image:
        return HttpResponse("Photo is unavailable.", status=404)
    return FileResponse(photo.image.open("rb"), as_attachment=True, filename=os.path.basename(photo.image.name))








