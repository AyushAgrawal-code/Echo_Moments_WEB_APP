import time
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections, models, transaction
from django.utils import timezone

from events.models import EventMember, FaceIndexJob, Photo, UploadJob


class Command(BaseCommand):
    help = "Process queued EchoMoments photo uploads. Run as a separate worker process."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process available jobs, then exit.")
        parser.add_argument("--poll-seconds", type=float, default=2.0)
        parser.add_argument("--guest-wait-seconds", type=int, default=30)
        parser.add_argument("--stale-after-seconds", type=int, default=300)
        parser.add_argument("--failed-retention-days", type=int, default=30)

    def handle(self, *args, **options):
        once = options["once"]
        poll_seconds = max(0.1, options["poll_seconds"])
        guest_wait = max(1, options["guest_wait_seconds"])
        stale_after = max(30, options["stale_after_seconds"])
        retention_days = max(1, options["failed_retention_days"])
        processed = 0
        next_cleanup = 0

        while True:
            close_old_connections()
            self._recover_stale_jobs(stale_after)
            if time.monotonic() >= next_cleanup:
                self._cleanup_expired_failed_jobs(retention_days)
                self._cleanup_old_terminal_staging()
                next_cleanup = time.monotonic() + 6 * 60 * 60
            job = self._claim_next_job(guest_wait)
            if job is None:
                if once:
                    self.stdout.write(f"Processed {processed} queued upload(s).")
                    return
                close_old_connections()
                time.sleep(poll_seconds)
                continue

            self._process(job)
            processed += 1
            close_old_connections()
            if once:
                # Continue until there are no currently available jobs.
                continue

    def _recover_stale_jobs(self, stale_after_seconds):
        now = timezone.now()
        cutoff = now - timedelta(seconds=stale_after_seconds)
        stale = UploadJob.objects.filter(
            status=UploadJob.Status.PROCESSING,
            updated_at__lte=cutoff,
        )
        stale.filter(attempts__lt=models.F("max_attempts")).update(
            status=UploadJob.Status.QUEUED,
            claim_token=None,
            available_at=now,
            error_message="Recovered after a worker restart; retrying.",
            updated_at=now,
        )
        exhausted = stale.filter(attempts__gte=models.F("max_attempts"))
        for job in exhausted:
            self._mark_failed(job, "Processing stopped before completion after the retry limit.")

    def _cleanup_expired_failed_jobs(self, retention_days):
        cutoff = timezone.now() - timedelta(days=retention_days)
        for job_id in UploadJob.objects.filter(
            status=UploadJob.Status.FAILED,
            finished_at__lte=cutoff,
        ).values_list("pk", flat=True):
            try:
                with transaction.atomic():
                    job = UploadJob.objects.select_for_update().filter(
                        pk=job_id,
                        status=UploadJob.Status.FAILED,
                        finished_at__lte=cutoff,
                    ).first()
                    if not job:
                        continue
                    if job.source_file:
                        job.source_file.delete(save=False)
                        job.source_file = ""
                        job.save(update_fields=["source_file", "updated_at"])
            except Exception as cleanup_error:
                self.stderr.write(f"Could not clean expired staged upload {job_id}: {cleanup_error}")

    def _cleanup_old_terminal_staging(self):
        cutoff = timezone.now() - timedelta(days=1)
        terminal_statuses = [UploadJob.Status.COMPLETE, UploadJob.Status.CANCELLED]
        for job_id in UploadJob.objects.filter(
            status__in=terminal_statuses,
            finished_at__lte=cutoff,
        ).exclude(source_file="").values_list("pk", flat=True):
            try:
                with transaction.atomic():
                    job = UploadJob.objects.select_for_update().filter(
                        pk=job_id,
                        status__in=terminal_statuses,
                        finished_at__lte=cutoff,
                    ).first()
                    if not job or not job.source_file:
                        continue
                    job.source_file.delete(save=False)
                    job.source_file = ""
                    job.save(update_fields=["source_file", "updated_at"])
            except Exception as cleanup_error:
                self.stderr.write(f"Could not clean terminal staged upload {job_id}: {cleanup_error}")

    def _claim_next_job(self, guest_wait_seconds):
        # A busy worker pool can race for the same first row. Retry selection
        # after a lost conditional claim instead of leaving this worker idle.
        for _ in range(16):
            now = timezone.now()
            available = UploadJob.objects.filter(
                status=UploadJob.Status.QUEUED,
                available_at__lte=now,
            )
            candidate = available.order_by("-priority", "created_at").first()
            if candidate is None:
                return None

            if candidate.priority > 0:
                overdue_guest = available.filter(
                    priority=0,
                    created_at__lte=now - timedelta(seconds=guest_wait_seconds),
                ).order_by("created_at").first()
                if overdue_guest and not UploadJob.objects.filter(
                    priority=0,
                    attempts__gt=0,
                    updated_at__gte=now - timedelta(seconds=guest_wait_seconds),
                ).exists():
                    # Hosts remain the normal first choice. When host work is
                    # continuously queued, allow one aged guest job per wait
                    # interval so guests do not starve indefinitely.
                    candidate = overdue_guest

            # Conditional update prevents two workers from claiming the same
            # item. PostgreSQL safely arbitrates across worker processes.
            claim_token = uuid.uuid4()
            claimed = UploadJob.objects.filter(
                pk=candidate.pk,
                status=UploadJob.Status.QUEUED,
                available_at__lte=now,
            ).update(
                status=UploadJob.Status.PROCESSING,
                attempts=candidate.attempts + 1,
                claim_token=claim_token,
                updated_at=now,
                error_message="",
            )
            if claimed:
                candidate.refresh_from_db()
                return candidate

        return None

    def _process(self, job):
        new_photo = None
        try:
            if job.uploader_id != job.event.created_by_id and not EventMember.objects.filter(
                event_id=job.event_id, user_id=job.uploader_id, is_active=True
            ).exists():
                self._cancel(job)
                return
            with transaction.atomic():
                locked_job = UploadJob.objects.select_for_update().get(pk=job.pk)
                if locked_job.status != UploadJob.Status.PROCESSING or locked_job.claim_token != job.claim_token:
                    return
                new_photo = Photo(event=locked_job.event, uploaded_by=locked_job.uploader)
                if not self._copy_staged_object(locked_job, new_photo):
                    with locked_job.source_file.open("rb") as source:
                        new_photo.image.save(locked_job.original_name, source, save=False)
                new_photo.save()
                new_photo.uploaded_at = locked_job.created_at
                new_photo.save(update_fields=["uploaded_at"])
                FaceIndexJob.objects.get_or_create(
                    photo=new_photo,
                    defaults={"available_at": timezone.now()},
                )
                locked_job.photo = new_photo
                locked_job.status = UploadJob.Status.COMPLETE
                locked_job.claim_token = None
                locked_job.finished_at = timezone.now()
                locked_job.error_message = ""
                locked_job.save(update_fields=["photo", "status", "claim_token", "finished_at", "error_message", "updated_at"])
            try:
                locked_job.source_file.delete(save=False)
            except Exception as cleanup_error:
                self.stderr.write(f"Could not remove staged file for {job.idempotency_key}: {cleanup_error}")
            self.stdout.write(f"Completed upload {job.idempotency_key}.")
        except Exception as exc:  # Temporary storage/database failures may recover.
            if new_photo and new_photo.image:
                new_photo.image.delete(save=False)
            self._retry_or_fail(job, str(exc))

    def _copy_staged_object(self, job, photo):
        """Move or copy between private storage prefixes server-side."""
        if getattr(settings, "USE_CLOUDINARY", False):
            try:
                from events.storage import CloudinaryPrivateStorage
                source_storage = job.source_file.storage
                dest_storage = photo.image.storage
                if isinstance(source_storage, CloudinaryPrivateStorage) and isinstance(dest_storage, CloudinaryPrivateStorage):
                    _, uploader, _ = CloudinaryPrivateStorage._sdk()
                    from_public_id = source_storage._public_id(job.source_file.name)
                    extension = Path(job.original_name).suffix.lower() or ".jpg"
                    destination_name = f"event_photos/{uuid.uuid4().hex}{extension}"
                    to_public_id = dest_storage._public_id(destination_name)
                    uploader.rename(
                        from_public_id,
                        to_public_id,
                        resource_type="image",
                        type="authenticated",
                        to_type="authenticated",
                        overwrite=True,
                    )
                    photo.image.name = destination_name
                    return True
            except Exception as exc:
                self.stderr.write(f"Cloudinary rename optimization failed, falling back to copy: {exc}")
                return False

        if not getattr(settings, "USE_S3", False):
            return False

        source_storage = job.source_file.storage
        destination_storage = photo.image.storage
        bucket_name = getattr(source_storage, "bucket_name", None)
        if not bucket_name or bucket_name != getattr(destination_storage, "bucket_name", None):
            return False

        source_normalize = getattr(source_storage, "_normalize_name", None)
        destination_normalize = getattr(destination_storage, "_normalize_name", None)
        if not callable(source_normalize) or not callable(destination_normalize):
            return False

        extension = Path(job.original_name).suffix.lower() or ".jpg"
        destination_name = f"event_photos/{uuid.uuid4().hex}{extension}"
        source_key = source_normalize(job.source_file.name)
        destination_key = destination_normalize(destination_name)
        source_storage.connection.meta.client.copy_object(
            Bucket=bucket_name,
            Key=destination_key,
            CopySource={"Bucket": bucket_name, "Key": source_key},
            MetadataDirective="COPY",
        )
        photo.image.name = destination_name
        return True

    def _mark_failed(self, job, message):
        updated = UploadJob.objects.filter(pk=job.pk, status=UploadJob.Status.PROCESSING, claim_token=job.claim_token).update(
            status=UploadJob.Status.FAILED,
            claim_token=None,
            error_message=message[:500],
            finished_at=timezone.now(),
            updated_at=timezone.now(),
        )
        if not updated:
            return

    def _cancel(self, job):
        now = timezone.now()
        updated = UploadJob.objects.filter(pk=job.pk, status=UploadJob.Status.PROCESSING, claim_token=job.claim_token).update(
            status=UploadJob.Status.CANCELLED,
            claim_token=None,
            error_message="Uploader no longer has active event membership.",
            finished_at=now,
            updated_at=now,
        )
        if not updated:
            return
        try:
            job.source_file.delete(save=False)
        except Exception as cleanup_error:
            self.stderr.write(f"Could not remove cancelled staged file for {job.idempotency_key}: {cleanup_error}")

    def _retry_or_fail(self, job, message):
        now = timezone.now()
        self.stderr.write(f"Upload job {job.idempotency_key} failed: {message}")
        if job.attempts < job.max_attempts:
            delay_seconds = min(60, 2 ** job.attempts)
            UploadJob.objects.filter(pk=job.pk, status=UploadJob.Status.PROCESSING, claim_token=job.claim_token).update(
                status=UploadJob.Status.QUEUED,
                claim_token=None,
                available_at=now + timedelta(seconds=delay_seconds),
                error_message="A temporary save problem occurred; retrying automatically.",
                updated_at=now,
            )
            return

        updated = UploadJob.objects.filter(pk=job.pk, status=UploadJob.Status.PROCESSING, claim_token=job.claim_token).update(
            status=UploadJob.Status.FAILED,
            claim_token=None,
            error_message="Could not save this photo after automatic retries. Use Retry photo to try again without selecting it again.",
            finished_at=now,
            updated_at=now,
        )
        if not updated:
            return
