import time
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import close_old_connections, models, transaction
from django.utils import timezone

from events.face_matching import (
    FaceMatchingUnavailable,
    create_analysis_image,
    decrypt_face_embeddings,
    decrypt_embedding,
    encrypt_face_embeddings,
    extract_face_embeddings,
    model_version,
    similarity,
)
from events.models import EventMember, FaceIndexJob, FaceMatch, Photo


class Command(BaseCommand):
    help = "Process queued face indexing for members who explicitly opted in."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--poll-seconds", type=float, default=2.0)
        parser.add_argument("--stale-after-seconds", type=int, default=300)
        parser.add_argument("--retry-failed", action="store_true", help="Requeue failed jobs, e.g. after installing face models.")

    def handle(self, *args, **options):
        once = options["once"]
        if options["retry_failed"]:
            now = timezone.now()
            FaceIndexJob.objects.filter(status=FaceIndexJob.Status.FAILED).update(
                status=FaceIndexJob.Status.QUEUED,
                attempts=0,
                generation=models.F("generation") + 1,
                available_at=now,
                error_message="",
                finished_at=None,
                updated_at=now,
            )
        processed = 0
        while True:
            close_old_connections()
            self._recover_stale(max(30, options["stale_after_seconds"]))
            job = self._claim()
            if not job:
                if once:
                    self.stdout.write(f"Processed {processed} face-index job(s).")
                    return
                close_old_connections()
                time.sleep(max(0.2, options["poll_seconds"]))
                continue
            self._process(job)
            processed += 1
            close_old_connections()

    def _recover_stale(self, seconds):
        now = timezone.now()
        stale = FaceIndexJob.objects.filter(
            status=FaceIndexJob.Status.PROCESSING,
            updated_at__lte=now - timedelta(seconds=seconds),
        )
        stale.filter(attempts__lt=models.F("max_attempts")).update(
            status=FaceIndexJob.Status.QUEUED,
            available_at=now,
            error_message="Recovered after worker restart; retrying.",
            updated_at=now,
        )
        stale.filter(attempts__gte=models.F("max_attempts")).update(
            status=FaceIndexJob.Status.FAILED,
            error_message="Indexing stopped before completion after the retry limit.",
            finished_at=now,
            updated_at=now,
        )

    def _claim(self):
        now = timezone.now()
        candidate = FaceIndexJob.objects.filter(
            status=FaceIndexJob.Status.QUEUED,
            available_at__lte=now,
        ).order_by("created_at").first()
        if not candidate:
            return None
        claimed = FaceIndexJob.objects.filter(
            pk=candidate.pk,
            status=FaceIndexJob.Status.QUEUED,
            available_at__lte=now,
        ).update(
            status=FaceIndexJob.Status.PROCESSING,
            attempts=candidate.attempts + 1,
            generation=models.F("generation") + 1,
            updated_at=now,
            error_message="",
        )
        if not claimed:
            return None
        candidate.refresh_from_db()
        return candidate

    def _process(self, job):
        now = timezone.now()
        generation = job.generation
        try:
            photo = job.photo
            members = list(EventMember.objects.filter(
                event_id=photo.event_id,
                is_active=True,
                face_consent_at__isnull=False,
            ).exclude(face_embedding_ciphertext="").only(
                "id", "user_id", "face_embedding_ciphertext", "face_model_version"
            ))
            matches = []
            if members:
                if not photo.image:
                    raise ValueError("The event photo is unavailable.")
                cached = (
                    photo.face_embeddings_ciphertext
                    and photo.face_embedding_model_version == model_version()
                )
                if cached:
                    image_embeddings = decrypt_face_embeddings(photo.face_embeddings_ciphertext)
                else:
                    with photo.image.open("rb") as source:
                        original_bytes = source.read()
                    if photo.analysis_image:
                        with photo.analysis_image.open("rb") as source:
                            analysis_bytes = source.read()
                    else:
                        analysis_bytes = create_analysis_image(original_bytes)
                        photo.analysis_image.save(f"face-scan-{photo.pk}.jpg", ContentFile(analysis_bytes), save=True)
                    image_embeddings = extract_face_embeddings(
                        analysis_bytes,
                        source_image_bytes=original_bytes,
                    )
                    if not image_embeddings:
                        # Preserve recall for distant faces missed at the smaller size.
                        image_embeddings = extract_face_embeddings(original_bytes)
                    Photo.objects.filter(pk=photo.pk).update(
                        face_embeddings_ciphertext=encrypt_face_embeddings(image_embeddings),
                        face_embedding_model_version=model_version(),
                    )
                threshold = float(getattr(settings, "FACE_MATCH_THRESHOLD", 0.5))
                for member in members:
                    if member.face_model_version != model_version():
                        # A model change requires the member to enroll again to
                        # avoid comparing vectors from incompatible models.
                        continue
                    enrollment = decrypt_embedding(member.face_embedding_ciphertext)
                    score = max((similarity(enrollment, vector) for vector in image_embeddings), default=0.0)
                    if score >= threshold:
                        matches.append(FaceMatch(photo=photo, user_id=member.user_id, similarity=score))

            with transaction.atomic():
                eligible_user_ids = set(EventMember.objects.select_for_update().filter(
                    event_id=photo.event_id,
                    is_active=True,
                    face_consent_at__isnull=False,
                ).exclude(face_embedding_ciphertext="").values_list("user_id", flat=True))
                current_job = FaceIndexJob.objects.select_for_update().get(pk=job.pk)
                if current_job.status != FaceIndexJob.Status.PROCESSING or current_job.generation != generation:
                    return
                FaceMatch.objects.filter(photo=photo).delete()
                FaceMatch.objects.bulk_create(
                    [match for match in matches if match.user_id in eligible_user_ids],
                    ignore_conflicts=True,
                )
                FaceIndexJob.objects.filter(
                    pk=job.pk,
                    status=FaceIndexJob.Status.PROCESSING,
                    generation=generation,
                ).update(
                    status=FaceIndexJob.Status.COMPLETE,
                    error_message="",
                    finished_at=now,
                    updated_at=now,
                )
            self.stdout.write(f"Indexed face suggestions for photo {photo.pk}.")
        except FaceMatchingUnavailable as exc:
            self._retry_or_fail(job, str(exc), generation, retry_delay=300)
            self.stderr.write(str(exc))
        except Exception as exc:
            self._retry_or_fail(job, str(exc), generation)
            self.stderr.write(f"Face-index job {job.pk} failed: {exc}")

    def _retry_or_fail(self, job, message, generation, retry_delay=None):
        now = timezone.now()
        if job.attempts < job.max_attempts:
            delay = retry_delay or min(300, 2 ** job.attempts)
            FaceIndexJob.objects.filter(pk=job.pk, status=FaceIndexJob.Status.PROCESSING, generation=generation).update(
                status=FaceIndexJob.Status.QUEUED,
                available_at=now + timedelta(seconds=delay),
                error_message=message[:500],
                updated_at=now,
            )
            return
        FaceIndexJob.objects.filter(pk=job.pk, status=FaceIndexJob.Status.PROCESSING, generation=generation).update(
            status=FaceIndexJob.Status.FAILED,
            error_message=message[:500],
            finished_at=now,
            updated_at=now,
        )
