from datetime import datetime
import logging
import os
import uuid
import tempfile
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, F
from PIL import Image, UnidentifiedImageError
from django.db import IntegrityError, transaction
from django.http import JsonResponse, HttpResponse, FileResponse, HttpResponseRedirect
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .models import Event, EventMember, FaceIndexJob, FaceMatch, Photo, UploadJob
from .image_validation import (
    SUPPORTED_IMAGE_FORMATS,
    safe_image_filename,
    validate_image_upload,
)
from .face_matching import (
    FaceEnrollmentError,
    FaceMatchingUnavailable,
    MAX_IMAGE_PIXELS,
    encrypt_embedding,
    extract_enrollment_embedding,
    model_version,
)

logger = logging.getLogger(__name__)
ALBUM_PAGE_SIZES = (20, 30, 50)


def _stored_image_type(image_file):
    """Return an allowlisted MIME type and extension inferred from image bytes."""
    if settings.USE_CLOUDINARY:
        # Every object in this backend is created from the validated image
        # upload path, so use its validated suffix instead of fetching it once
        # for MIME sniffing and then fetching it again to serve the response.
        cloudinary_types = {
            ".jpg": ("image/jpeg", "jpg"),
            ".jpeg": ("image/jpeg", "jpg"),
            ".png": ("image/png", "png"),
            ".gif": ("image/gif", "gif"),
            ".webp": ("image/webp", "webp"),
        }
        return cloudinary_types.get(os.path.splitext(image_file.name)[1].lower())
    try:
        with image_file.open("rb") as source:
            with Image.open(source) as image:
                return SUPPORTED_IMAGE_FORMATS.get(image.format)
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        return None


def _album_page_size(request):
    try:
        requested = int(request.GET.get("page_size", "20"))
    except (TypeError, ValueError):
        requested = 20
    return requested if requested in ALBUM_PAGE_SIZES else 20


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


def _member_upload_limit(event, membership):
    if membership.photo_limit_override is not None:
        return membership.photo_limit_override
    if event.member_photo_limit_enabled:
        return event.default_member_photo_limit
    return None


def _has_active_face_enrollment(membership):
    return bool(membership and membership.face_consent_at and membership.face_embedding_ciphertext)


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
def accept_event_invite(request, invite_token):
    event = get_object_or_404(Event, invite_token=invite_token)
    if event.privacy != "private":
        return HttpResponse("This invitation is no longer valid.", status=404)
    if not event.is_active:
        return render(request, "events/event_unavailable.html", {"event": event}, status=410)
    membership, created = EventMember.objects.get_or_create(
        user=request.user,
        event=event,
        defaults={"join_method": "invite", "role": "guest", "is_active": True},
    )
    if not created and not membership.is_active:
        messages.error(request, "Your membership in this event is inactive.")
        return redirect("accounts:dashboard")
    return redirect("events:event_detail", event_code=event.event_code)


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
        cover_photo = request.FILES.get("cover_photo")
        if cover_photo:
            try:
                _, extension = validate_image_upload(cover_photo)
                cover_photo.name = safe_image_filename(cover_photo.name, extension)
            except ValidationError as exc:
                return JsonResponse({"success": False, "error": "; ".join(exc.messages)}, status=400)
        try:
            with transaction.atomic():
                event = Event.objects.create(
                    created_by=request.user, event_name=name, event_date=event_date,
                    event_time=request.POST.get("event_time") or None,
                    location=request.POST.get("location", "").strip(),
                    description=request.POST.get("description", "").strip(),
                    privacy=privacy, theme_color=theme,
                    cover_photo=cover_photo,
                    allow_upload="allow_upload" in request.POST,
                    allow_download="allow_download" in request.POST,
                    allow_tag=False,
                    allow_comment=False,
                )
                EventMember.objects.create(user=request.user, event=event, role="host", join_method="code")
        except (ValidationError, ValueError) as exc:
            return JsonResponse({"success": False, "error": str(exc)}, status=400)
        if event.privacy == "private":
            join_url = request.build_absolute_uri(reverse("events:accept_event_invite", args=[event.invite_token]))
        else:
            join_url = request.build_absolute_uri(reverse("events:join_event")) + "?event_code=" + event.event_code
        return JsonResponse({
            "success": True,
            "event_code": event.event_code,
            "privacy": event.privacy,
            "url": reverse("events:event_detail", args=[event.event_code]),
            "join_url": join_url,
        }, status=201)
    return render(request, "events/host.html")


@login_required
def event_detail(request, event_code):
    event = get_object_or_404(Event, event_code=event_code)
    if not _can_view(event, request.user):
        if not event.is_active:
            return render(request, "events/event_unavailable.html", {"event": event}, status=410)
        return HttpResponse("You do not have access to this event.", status=403)
    is_host = _is_host(event, request.user)
    active_members = event.memberships.filter(is_active=True)
    active_member_count = active_members.count()
    member_page = None
    if is_host:
        member_queryset = active_members.select_related("user").annotate(
            photo_count=Count("user__uploaded_photos", filter=Q(user__uploaded_photos__event=event))
        ).order_by("-joined_at", "pk")
        member_page = Paginator(member_queryset, 50).get_page(request.GET.get("members_page"))
        members = member_page.object_list
    else:
        members = ()
    photo_queryset = event.photos.order_by("-uploaded_at", "-pk")
    stored_photo_count = photo_queryset.count()
    page_size = _album_page_size(request)
    photo_page = Paginator(photo_queryset, page_size).get_page(request.GET.get("page"))
    photos = photo_page.object_list
    pending_jobs = event.upload_jobs.filter(
        status__in=[UploadJob.Status.QUEUED, UploadJob.Status.PROCESSING]
    )
    pending_count = pending_jobs.count()
    host_photo_count = Photo.objects.filter(event=event, uploaded_by=event.created_by).count()
    membership = _membership(event, request.user)
    host_capacity_used = host_photo_count + pending_jobs.filter(uploader=event.created_by).count()
    guest_capacity_used = stored_photo_count - host_photo_count + pending_jobs.exclude(uploader=event.created_by).count()
    member_capacity_used = Photo.objects.filter(event=event, uploaded_by=request.user).count()
    member_capacity_used += pending_jobs.filter(uploader=request.user).count()
    upload_block_reason = ""
    if not event.is_active:
        upload_block_reason = "This event has ended; its album remains available."
    elif not event.allow_upload:
        upload_block_reason = "The host has paused uploads."
    elif membership is None:
        upload_block_reason = "Join this event before uploading."
    elif not is_host and not membership.can_upload:
        upload_block_reason = "The host has set your access to view-only."
    elif event.max_photo_count is not None and stored_photo_count + pending_count >= event.max_photo_count:
        upload_block_reason = "The event photo limit has been reached."
    elif is_host and event.host_photo_limit is not None and host_capacity_used >= event.host_photo_limit:
        upload_block_reason = "The host photo allocation is full."
    elif not is_host and event.guest_photo_pool_limit is not None and guest_capacity_used >= event.guest_photo_pool_limit:
        upload_block_reason = "The guest photo pool is full."
    elif (
        not is_host
        and membership is not None
        and _member_upload_limit(event, membership) is not None
        and member_capacity_used >= _member_upload_limit(event, membership)
    ):
        upload_block_reason = "You have reached your photo upload limit."
    upload_jobs = event.upload_jobs.select_related("uploader", "photo").order_by("-created_at")
    if not is_host:
        upload_jobs = upload_jobs.filter(uploader=request.user)
    upload_jobs = upload_jobs[:20]
    share_url = (
        request.build_absolute_uri(reverse("events:accept_event_invite", args=[event.invite_token]))
        if event.privacy == "private"
        else request.build_absolute_uri(reverse("events:join_event")) + "?event_code=" + event.event_code
    )
    context = {"event": event, "members": members, "photos": photos,
               "share_url": share_url,
               "is_host": is_host,
               "membership": membership,
               "member_page": member_page,
        "face_enrolled": _has_active_face_enrollment(membership),
               "my_face_match_count": FaceMatch.objects.filter(photo__event=event, user=request.user, is_hidden=False).count(),
               "can_upload_now": not upload_block_reason,
               "upload_block_reason": upload_block_reason,
               "upload_jobs": upload_jobs,
               "photo_page": photo_page,
               "photo_page_size": page_size,
               "photo_page_sizes": ALBUM_PAGE_SIZES,
               "stats": {
                   "total_photos": stored_photo_count,
                   "active_guests": active_member_count,
                   "recent_uploads": photo_queryset[:3],
                   "capacity_used": stored_photo_count + pending_count,
                   "host_capacity_used": host_capacity_used,
                   "guest_capacity_used": guest_capacity_used,
               }}
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
    if not _can_view(event, request.user):
        return JsonResponse({"success": False, "error": "Event access is required."}, status=403)
    membership = _membership(event, request.user)
    if not membership:
        return JsonResponse({"success": False, "error": "Join this event to upload."}, status=403)
    if not _is_host(event, request.user) and not membership.can_upload:
        return JsonResponse({"success": False, "error": "Your event membership is view-only."}, status=403)
    if not event.is_active or not event.allow_upload:
        return JsonResponse({"success": False, "error": "Uploads are not available for this event."}, status=403)
    files = request.FILES.getlist("images") or request.FILES.getlist("image")
    if not files:
        return JsonResponse({"success": False, "error": "Choose at least one image."}, status=400)
    if len(files) > 20:
        return JsonResponse({"success": False, "error": "Upload at most 20 images at a time."}, status=400)
    if len(files) != 1:
        return JsonResponse({"success": False, "error": "Upload each photo as a separate queue item."}, status=400)

    image = files[0]
    try:
        image_info = validate_image_upload(image)
    except ValidationError as exc:
        status_code = 413 if exc.code == "image_too_many_pixels" else 400
        return JsonResponse({"success": False, "error": "; ".join(exc.messages)}, status=status_code)

    try:
        upload_key = uuid.UUID(request.POST.get("client_upload_id", ""))
    except (ValueError, TypeError, AttributeError):
        upload_key = uuid.uuid4()
    safe_original_name = safe_image_filename(image.name, image_info[1])

    existing = UploadJob.objects.filter(
        event=event, uploader=request.user, idempotency_key=upload_key
    ).first()
    if existing:
        return JsonResponse({"success": True, "job_id": str(existing.idempotency_key), "status": existing.status}, status=202)

    try:
        with transaction.atomic():
            locked_event = Event.objects.select_for_update().get(pk=event.pk)
            if not locked_event.is_active or not locked_event.allow_upload:
                return JsonResponse({"success": False, "error": "Uploads are not available for this event."}, status=403)
            membership = EventMember.objects.select_for_update().filter(
                event=locked_event, user=request.user, is_active=True
            ).first()
            if not membership:
                return JsonResponse({"success": False, "error": "Join this event to upload."}, status=403)
            is_host = _is_host(locked_event, request.user)
            if not is_host and not membership.can_upload:
                return JsonResponse({"success": False, "error": "Your event membership is view-only."}, status=403)
            # Queued jobs reserve capacity so simultaneous uploads cannot exceed
            # a configured cap while waiting for the worker.
            active_jobs = UploadJob.objects.filter(
                event=locked_event, status__in=[UploadJob.Status.QUEUED, UploadJob.Status.PROCESSING]
            )
            total_used = Photo.objects.filter(event=locked_event).count() + active_jobs.count()
            if locked_event.max_photo_count is not None and total_used >= locked_event.max_photo_count:
                return JsonResponse({"success": False, "error": "This event has reached its photo limit."}, status=409)

            is_host = _is_host(locked_event, request.user)
            if is_host:
                role_used = (
                    Photo.objects.filter(event=locked_event, uploaded_by=request.user).count()
                    + active_jobs.filter(uploader=request.user).count()
                )
                role_limit = locked_event.host_photo_limit
                if role_limit is not None and role_used >= role_limit:
                    return JsonResponse({"success": False, "error": "The host photo allocation is full."}, status=409)
            else:
                guest_photos = Photo.objects.filter(event=locked_event).filter(
                    Q(uploaded_by__isnull=True) | ~Q(uploaded_by_id=locked_event.created_by_id)
                ).count()
                guest_jobs = active_jobs.exclude(uploader_id=locked_event.created_by_id).count()
                if locked_event.guest_photo_pool_limit is not None and guest_photos + guest_jobs >= locked_event.guest_photo_pool_limit:
                    return JsonResponse({"success": False, "error": "The guest photo pool is full."}, status=409)

                member_limit = _member_upload_limit(locked_event, membership)
                if member_limit is not None:
                    member_used = (
                        Photo.objects.filter(event=locked_event, uploaded_by=request.user).count()
                        + active_jobs.filter(uploader=request.user).count()
                    )
                    if member_used >= member_limit:
                        return JsonResponse({"success": False, "error": "You have reached your photo upload limit."}, status=409)

            job = UploadJob(
                event=locked_event,
                uploader=request.user,
                original_name=safe_original_name,
                idempotency_key=upload_key,
                priority=100 if is_host else 0,
                available_at=timezone.now(),
            )
            job.source_file.save(job.original_name, image, save=False)
            job.save()
    except IntegrityError:
        if "job" in locals() and job.source_file:
            job.source_file.delete(save=False)
        existing = UploadJob.objects.filter(
            event=event, uploader=request.user, idempotency_key=upload_key
        ).first()
        if existing:
            return JsonResponse({"success": True, "job_id": str(existing.idempotency_key), "status": existing.status}, status=202)
        return JsonResponse({"success": False, "error": "This upload could not be queued. Please retry."}, status=409)
    except (ValidationError, OSError, ValueError) as exc:
        if "job" in locals() and job.source_file:
            job.source_file.delete(save=False)
        return JsonResponse({"success": False, "error": str(exc) or "The photo could not be queued."}, status=400)
    except Exception:
        if "job" in locals() and job.source_file:
            job.source_file.delete(save=False)
        return JsonResponse({"success": False, "error": "The photo could not be queued."}, status=500)
    return JsonResponse({"success": True, "job_id": str(job.idempotency_key), "status": job.status}, status=202)


@login_required
def upload_job_status(request, event_code, job_id):
    event = get_object_or_404(Event, event_code=event_code)
    if not _can_view(event, request.user):
        return JsonResponse({"success": False, "error": "Event access is required."}, status=403)
    job = get_object_or_404(UploadJob, event=event, idempotency_key=job_id)
    if not _is_host(event, request.user) and (
        job.uploader_id != request.user.id or not _membership(event, request.user)
    ):
        return JsonResponse({"success": False, "error": "This upload does not belong to you."}, status=403)
    return JsonResponse({
        "success": True,
        "job_id": str(job.idempotency_key),
        "status": job.status,
        "attempts": job.attempts,
        "error": job.error_message,
        "can_retry": bool(
            job.status == UploadJob.Status.FAILED
            and job.source_file
            and job.source_file.storage.exists(job.source_file.name)
        ),
    })


@login_required
@require_POST
def retry_upload_job(request, event_code, job_id):
    event = get_object_or_404(Event, event_code=event_code)
    if not _can_view(event, request.user):
        return JsonResponse({"success": False, "error": "Event access is required."}, status=403)

    now = timezone.now()
    with transaction.atomic():
        event = Event.objects.select_for_update().get(pk=event.pk)
        job = get_object_or_404(
            UploadJob.objects.select_for_update(), event=event, idempotency_key=job_id
        )
        if not _is_host(event, request.user) and job.uploader_id != request.user.id:
            return JsonResponse({"success": False, "error": "This upload does not belong to you."}, status=403)
        if job.status != UploadJob.Status.FAILED:
            return JsonResponse({"success": False, "error": "Only failed uploads can be retried."}, status=409)
        if not event.is_active or not event.allow_upload:
            return JsonResponse({"success": False, "error": "Uploads are not available for this event."}, status=410)
        if not job.source_file or not job.source_file.storage.exists(job.source_file.name):
            return JsonResponse({"success": False, "error": "The private staged file has expired. Select the photo again to upload it."}, status=410)

        uploader_is_host = job.uploader_id == event.created_by_id
        uploader_membership = EventMember.objects.select_for_update().filter(
            event=event, user_id=job.uploader_id, is_active=True
        ).first()
        if not uploader_membership:
            return JsonResponse({"success": False, "error": "The uploader no longer has access to this event."}, status=410)
        if not uploader_is_host and not uploader_membership.can_upload:
            return JsonResponse({"success": False, "error": "This member is currently view-only."}, status=409)

        active_jobs = UploadJob.objects.filter(
            event=event,
            status__in=[UploadJob.Status.QUEUED, UploadJob.Status.PROCESSING],
        )
        total_used = Photo.objects.filter(event=event).count() + active_jobs.count()
        if event.max_photo_count is not None and total_used >= event.max_photo_count:
            return JsonResponse({"success": False, "error": "The event photo limit is full."}, status=409)
        if uploader_is_host:
            host_used = (
                Photo.objects.filter(event=event, uploaded_by=event.created_by).count()
                + active_jobs.filter(uploader=event.created_by).count()
            )
            if event.host_photo_limit is not None and host_used >= event.host_photo_limit:
                return JsonResponse({"success": False, "error": "The host photo allocation is full."}, status=409)
        else:
            guest_used = (
                Photo.objects.filter(event=event).filter(
                    Q(uploaded_by__isnull=True) | ~Q(uploaded_by_id=event.created_by_id)
                ).count()
                + active_jobs.exclude(uploader_id=event.created_by_id).count()
            )
            if event.guest_photo_pool_limit is not None and guest_used >= event.guest_photo_pool_limit:
                return JsonResponse({"success": False, "error": "The guest photo pool is full."}, status=409)
            member_limit = _member_upload_limit(event, uploader_membership)
            if member_limit is not None:
                member_used = (
                    Photo.objects.filter(event=event, uploaded_by_id=job.uploader_id).count()
                    + active_jobs.filter(uploader_id=job.uploader_id).count()
                )
                if member_used >= member_limit:
                    return JsonResponse({"success": False, "error": "The member photo limit is full."}, status=409)

        job.status = UploadJob.Status.QUEUED
        job.priority = 100 if uploader_is_host else 0
        job.attempts = 0
        job.claim_token = None
        job.available_at = now
        job.error_message = ""
        job.finished_at = None
        job.save(update_fields=[
            "status", "priority", "attempts", "claim_token", "available_at",
            "error_message", "finished_at", "updated_at",
        ])
    return JsonResponse({"success": True, "job_id": str(job.idempotency_key), "status": job.status}, status=202)


def _parse_optional_limit(value, label):
    value = (value or "").strip()
    if not value:
        return None
    try:
        limit = int(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a whole number or blank.") from exc
    if limit < 0:
        raise ValueError(f"{label} cannot be negative.")
    return limit


@login_required
@require_POST
def update_photo_limits(request, event_code):
    event = get_object_or_404(Event, event_code=event_code)
    if not _is_host(event, request.user):
        return JsonResponse({"success": False, "error": "Host access required."}, status=403)
    try:
        max_photos = _parse_optional_limit(request.POST.get("max_photo_count"), "Event limit")
        host_limit = _parse_optional_limit(request.POST.get("host_photo_limit"), "Host limit")
        guest_limit = _parse_optional_limit(request.POST.get("guest_photo_pool_limit"), "Guest pool")
        default_member_limit = _parse_optional_limit(request.POST.get("default_member_photo_limit"), "Per-member limit")
    except ValueError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)
    if max_photos is not None and host_limit is not None and guest_limit is not None and host_limit + guest_limit > max_photos:
        return JsonResponse({"success": False, "error": "Host and guest allocations cannot exceed the event limit."}, status=400)
    with transaction.atomic():
        event = Event.objects.select_for_update().get(pk=event.pk)
        active_jobs = UploadJob.objects.filter(
            event=event, status__in=[UploadJob.Status.QUEUED, UploadJob.Status.PROCESSING]
        )
        total_in_use = Photo.objects.filter(event=event).count() + active_jobs.count()
        host_in_use = (
            Photo.objects.filter(event=event, uploaded_by=event.created_by).count()
            + active_jobs.filter(uploader=event.created_by).count()
        )
        guest_in_use = (
            Photo.objects.filter(event=event).filter(
                Q(uploaded_by__isnull=True) | ~Q(uploaded_by_id=event.created_by_id)
            ).count()
            + active_jobs.exclude(uploader=event.created_by).count()
        )
        if max_photos is not None and total_in_use > max_photos:
            return JsonResponse({"success": False, "error": "The event cap cannot be lower than saved and queued photos."}, status=409)
        if host_limit is not None and host_in_use > host_limit:
            return JsonResponse({"success": False, "error": "The host cap cannot be lower than saved and queued host photos."}, status=409)
        if guest_limit is not None and guest_in_use > guest_limit:
            return JsonResponse({"success": False, "error": "The guest pool cannot be lower than saved and queued guest photos."}, status=409)
        event.max_photo_count = max_photos
        event.host_photo_limit = host_limit
        event.guest_photo_pool_limit = guest_limit
        event.member_photo_limit_enabled = request.POST.get("member_photo_limit_enabled") == "on"
        event.default_member_photo_limit = default_member_limit
        event.save(update_fields=[
            "max_photo_count", "host_photo_limit", "guest_photo_pool_limit",
            "member_photo_limit_enabled", "default_member_photo_limit", "updated_at",
        ])
    return JsonResponse({"success": True})


@login_required
@require_POST
def update_member_photo_limit(request, event_code, user_id):
    event = get_object_or_404(Event, event_code=event_code)
    if not _is_host(event, request.user):
        return JsonResponse({"success": False, "error": "Host access required."}, status=403)
    try:
        limit = _parse_optional_limit(request.POST.get("photo_limit_override"), "Member limit")
    except ValueError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)
    with transaction.atomic():
        event = Event.objects.select_for_update().get(pk=event.pk)
        membership = get_object_or_404(EventMember.objects.select_for_update(), event=event, user_id=user_id)
        if membership.user_id == event.created_by_id:
            return JsonResponse({"success": False, "error": "Use the host allocation setting for the host."}, status=400)
        if limit is not None:
            active_jobs = UploadJob.objects.filter(
                event=event,
                uploader=membership.user,
                status__in=[UploadJob.Status.QUEUED, UploadJob.Status.PROCESSING],
            ).count()
            uploaded = Photo.objects.filter(event=event, uploaded_by=membership.user).count()
            if uploaded + active_jobs > limit:
                return JsonResponse({"success": False, "error": "The member cap cannot be lower than their saved and queued photos."}, status=409)
        membership.photo_limit_override = limit
        membership.can_upload = request.POST.get("can_upload") == "on"
        membership.save(update_fields=["photo_limit_override", "can_upload"])
    return JsonResponse({"success": True})


@login_required
@require_POST
def remove_member(request, event_code, user_id):
    event = get_object_or_404(Event, event_code=event_code)
    if not _is_host(event, request.user):
        return JsonResponse({"success": False, "error": "Host access required."}, status=403)
    if not event.is_active:
        return JsonResponse({"success": False, "error": "Event has ended."}, status=410)
    with transaction.atomic():
        event = Event.objects.select_for_update().get(pk=event.pk)
        membership = get_object_or_404(
            EventMember.objects.select_for_update(), event=event, user_id=user_id, is_active=True
        )
        if membership.role == "host" or membership.user_id == event.created_by_id:
            return JsonResponse({"success": False, "error": "The host cannot be removed."}, status=400)
        membership.is_active = False
        membership.face_embedding_ciphertext = ""
        membership.face_consent_at = None
        membership.face_model_version = ""
        membership.save(update_fields=["is_active", "face_embedding_ciphertext", "face_consent_at", "face_model_version"])
        FaceMatch.objects.filter(user=membership.user, photo__event=event).delete()
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
    if not _can_view(event, request.user):
        return JsonResponse({"success": False, "error": "Event membership required."}, status=403)
    if photo.uploaded_by_id != request.user.id and not _is_host(event, request.user):
        return JsonResponse({"success": False, "error": "You can only delete your own uploads."}, status=403)
    image = photo.image
    photo.delete()
    if image:
        image.delete(save=False)
    return JsonResponse({"success": True})


@login_required
def view_photo(request, event_code, photo_id):
    event = get_object_or_404(Event, event_code=event_code)
    if not _can_view(event, request.user):
        return HttpResponse("Event membership required.", status=403)
    photo = get_object_or_404(Photo, event=event, pk=photo_id)
    if not photo.image:
        return HttpResponse("Photo is unavailable.", status=404)
    image_info = _stored_image_type(photo.image)
    if not image_info:
        return HttpResponse("Photo is unavailable.", status=404)
    content_type, extension = image_info
    if getattr(settings, "USE_CLOUDINARY", False) or getattr(settings, "USE_S3", False):
        return HttpResponseRedirect(photo.image.url)
    response = FileResponse(
        photo.image.open("rb"),
        as_attachment=False,
        filename=f"photo-{photo.pk}.{extension}",
        content_type=content_type,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def view_event_cover(request, event_code):
    event = get_object_or_404(Event, event_code=event_code)
    if not _can_view(event, request.user):
        return HttpResponse("Event membership required.", status=403)
    if not event.cover_photo:
        return HttpResponse("Cover photo is unavailable.", status=404)
    image_info = _stored_image_type(event.cover_photo)
    if not image_info:
        return HttpResponse("Cover photo is unavailable.", status=404)
    content_type, extension = image_info
    if getattr(settings, "USE_CLOUDINARY", False) or getattr(settings, "USE_S3", False):
        return HttpResponseRedirect(event.cover_photo.url)
    response = FileResponse(
        event.cover_photo.open("rb"),
        as_attachment=False,
        filename=f"event-cover-{event.event_code}.{extension}",
        content_type=content_type,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


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
    image_info = _stored_image_type(photo.image)
    if not image_info:
        return HttpResponse("Photo is unavailable.", status=404)
    content_type, extension = image_info
    if getattr(settings, "USE_CLOUDINARY", False):
        storage = photo.image.storage
        if hasattr(storage, "_signed_url"):
            signed_url = storage._signed_url(photo.image.name, expires_in=300, attachment=True)
            return HttpResponseRedirect(signed_url)
        return HttpResponseRedirect(photo.image.url)
    response = FileResponse(
        photo.image.open("rb"),
        as_attachment=True,
        filename=f"photo-{photo.pk}.{extension}",
        content_type=content_type,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _my_photos_context(request, event, membership, face_error="", enrollment_error=""):
    match_queryset = FaceMatch.objects.filter(
        user=request.user,
        photo__event=event,
        is_hidden=False,
    ).select_related("photo").order_by("-photo__uploaded_at", "-pk")
    if not _has_active_face_enrollment(membership):
        match_queryset = FaceMatch.objects.none()
    match_count = match_queryset.count()
    page_size = _album_page_size(request)
    match_page = Paginator(match_queryset, page_size).get_page(request.GET.get("page"))
    pending_count = FaceIndexJob.objects.filter(
        photo__event=event,
        status__in=[FaceIndexJob.Status.QUEUED, FaceIndexJob.Status.PROCESSING],
    ).count()
    failed_count = FaceIndexJob.objects.filter(
        photo__event=event,
        status=FaceIndexJob.Status.FAILED,
    ).count()
    face_scan_complete = FaceIndexJob.objects.filter(
        photo__event=event,
        status=FaceIndexJob.Status.COMPLETE,
    ).count()
    return {
        "event": event,
        "membership": membership,
        "matches": match_page.object_list,
        "match_page": match_page,
        "photo_page_size": page_size,
        "photo_page_sizes": ALBUM_PAGE_SIZES,
        "matches_count": match_count,
        "pending_count": pending_count,
        "failed_count": failed_count,
        "face_scan_complete": face_scan_complete,
        "face_scan_total": face_scan_complete + pending_count + failed_count,
        "face_enrolled": _has_active_face_enrollment(membership),
        "is_host": _is_host(event, request.user),
        "face_error": face_error,
        "enrollment_error": enrollment_error,
    }


@login_required
def my_photos(request, event_code):
    event = get_object_or_404(Event, event_code=event_code)
    membership = _membership(event, request.user)
    if not membership or not _can_view(event, request.user):
        return HttpResponse("Event membership required.", status=403)
    return render(request, "events/my_photos.html", _my_photos_context(request, event, membership))


@login_required
def face_scan_status(request, event_code):
    """Return aggregate progress for the current member's event photo scan."""
    event = get_object_or_404(Event, event_code=event_code)
    if not _membership(event, request.user) or not _can_view(event, request.user):
        return JsonResponse({"error": "Event membership required."}, status=403)

    counts = FaceIndexJob.objects.filter(photo__event=event).aggregate(
        total=Count("pk"),
        complete=Count("pk", filter=Q(status=FaceIndexJob.Status.COMPLETE)),
        queued=Count("pk", filter=Q(status=FaceIndexJob.Status.QUEUED)),
        processing=Count("pk", filter=Q(status=FaceIndexJob.Status.PROCESSING)),
        failed=Count("pk", filter=Q(status=FaceIndexJob.Status.FAILED)),
    )
    response = JsonResponse(counts)
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_POST
def enroll_face(request, event_code):
    event = get_object_or_404(Event, event_code=event_code)
    membership = _membership(event, request.user)
    if not membership or not _can_view(event, request.user):
        return HttpResponse("Active event membership required.", status=403)
    is_replacing_template = _has_active_face_enrollment(membership)
    if request.POST.get("face_consent") != "on":
        messages.error(request, "Please agree before enabling face matching.")
        return redirect("events:my_photos", event_code=event.event_code)
    selfie = request.FILES.get("selfie")
    if not selfie:
        messages.error(request, "Choose a clear selfie to find your photos.")
        return redirect("events:my_photos", event_code=event.event_code)
    try:
        validate_image_upload(selfie)
        embedding = extract_enrollment_embedding(selfie.read())
        ciphertext = encrypt_embedding(embedding)
    except FaceMatchingUnavailable as exc:
        logger.error("Face enrollment unavailable for event %s: %s", event.pk, exc)
        context = _my_photos_context(
            request,
            event,
            membership,
            face_error="Face matching is temporarily unavailable on this server. Your selfie was not saved. Please try again later.",
        )
        return render(request, "events/my_photos.html", context, status=503)
    except (FaceEnrollmentError, ValidationError, UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        context = _my_photos_context(
            request,
            event,
            membership,
            enrollment_error=str(exc) or "The selfie could not be read.",
        )
        return render(request, "events/my_photos.html", context, status=400)

    now = timezone.now()
    with transaction.atomic():
        locked_membership = EventMember.objects.select_for_update().get(pk=membership.pk)
        locked_membership.face_embedding_ciphertext = ciphertext
        locked_membership.face_consent_at = now
        locked_membership.face_model_version = model_version()
        locked_membership.save(update_fields=["face_embedding_ciphertext", "face_consent_at", "face_model_version"])
        FaceMatch.objects.filter(user=request.user, photo__event=event).delete()

        FaceIndexJob.objects.filter(photo__event=event).update(
            status=FaceIndexJob.Status.QUEUED,
            attempts=0,
            generation=F("generation") + 1,
            available_at=now,
            error_message="",
            finished_at=None,
            updated_at=now,
        )
        photo_ids = Photo.objects.filter(event=event).filter(
            face_index_job__isnull=True
        ).values_list("pk", flat=True).iterator(chunk_size=500)
        batch = []
        for photo_id in photo_ids:
            batch.append(FaceIndexJob(photo_id=photo_id, available_at=now))
            if len(batch) == 500:
                FaceIndexJob.objects.bulk_create(batch, ignore_conflicts=True)
                batch.clear()
        if batch:
            FaceIndexJob.objects.bulk_create(batch, ignore_conflicts=True)
    if is_replacing_template:
        messages.success(request, "Your face template was updated. Event photos are being rescanned; the new selfie is not stored.")
    else:
        messages.success(request, "Face matching is on. Your event photos are being scanned; the selfie is not stored.")
    return redirect("events:my_photos", event_code=event.event_code)


@login_required
@require_POST
def revoke_face_enrollment(request, event_code):
    event = get_object_or_404(Event, event_code=event_code)
    membership = _membership(event, request.user)
    if not membership:
        return HttpResponse("Active event membership required.", status=403)
    with transaction.atomic():
        membership = EventMember.objects.select_for_update().get(pk=membership.pk)
        membership.face_embedding_ciphertext = ""
        membership.face_consent_at = None
        membership.face_model_version = ""
        membership.save(update_fields=["face_embedding_ciphertext", "face_consent_at", "face_model_version"])
        FaceMatch.objects.filter(user=request.user, photo__event=event).delete()
        if not EventMember.objects.filter(
            event=event,
            is_active=True,
            face_consent_at__isnull=False,
        ).exclude(face_embedding_ciphertext="").exists():
            Photo.objects.filter(event=event).update(
                face_embeddings_ciphertext="",
                face_embedding_model_version="",
            )
    messages.success(request, "Face matching is off and your saved face template and suggestions were deleted.")
    return redirect("events:my_photos", event_code=event.event_code)


@login_required
@require_POST
def retry_face_indexing(request, event_code):
    event = get_object_or_404(Event, event_code=event_code)
    if not _is_host(event, request.user):
        return HttpResponse("Host access required.", status=403)
    now = timezone.now()
    failed_jobs = FaceIndexJob.objects.filter(photo__event=event, status=FaceIndexJob.Status.FAILED)
    count = failed_jobs.update(
        status=FaceIndexJob.Status.QUEUED,
        attempts=0,
        generation=F("generation") + 1,
        available_at=now,
        error_message="",
        finished_at=None,
        updated_at=now,
    )
    messages.success(request, f"Queued {count} failed face scan(s) for retry.")
    return redirect("events:my_photos", event_code=event.event_code)


@login_required
@require_POST
def hide_face_match(request, event_code, photo_id):
    event = get_object_or_404(Event, event_code=event_code)
    membership = _membership(event, request.user)
    if not _can_view(event, request.user) or not _has_active_face_enrollment(membership):
        return HttpResponse("Active face enrollment required.", status=403)
    match = get_object_or_404(FaceMatch, photo__event=event, photo_id=photo_id, user=request.user)
    match.is_hidden = True
    match.save(update_fields=["is_hidden"])
    return redirect("events:my_photos", event_code=event.event_code)


@login_required
@require_http_methods(["GET", "POST"])
def download_my_photos(request, event_code):
    event = get_object_or_404(Event, event_code=event_code)
    membership = _membership(event, request.user)
    if not _can_view(event, request.user) or not _has_active_face_enrollment(membership):
        return HttpResponse("Active face enrollment required.", status=403)
    if not event.allow_download:
        return HttpResponse("Downloads are disabled for this event.", status=403)
    visible_matches = Photo.objects.filter(
        face_matches__user=request.user,
        face_matches__is_hidden=False,
        event=event,
    ).distinct()
    if request.method == "POST":
        raw_photo_ids = request.POST.getlist("photo_ids")
        try:
            selected_photo_ids = {int(photo_id) for photo_id in raw_photo_ids}
        except (TypeError, ValueError):
            return HttpResponse("Invalid selected photo.", status=400)
        if not selected_photo_ids:
            messages.error(request, "Select at least one photo to download.")
            return redirect("events:my_photos", event_code=event.event_code)
        photos = visible_matches.filter(pk__in=selected_photo_ids).order_by("uploaded_at", "pk")
        if photos.count() != len(selected_photo_ids):
            return HttpResponse("Selected photos must be visible matches in your album.", status=403)
    else:
        photos = visible_matches.order_by("uploaded_at", "pk")
    archive = tempfile.NamedTemporaryFile(mode="w+b", suffix=".zip")
    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for photo in photos:
            if not photo.image:
                continue
            try:
                image_info = _stored_image_type(photo.image)
                if not image_info:
                    continue
                _, extension = image_info
                with photo.image.open("rb") as source:
                    zipped.writestr(f"photo-{photo.pk}.{extension}", source.read())
            except OSError:
                continue
    archive.seek(0)
    response = FileResponse(archive, as_attachment=True, filename=f"{event.event_code}-my-photos.zip", content_type="application/zip")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response








