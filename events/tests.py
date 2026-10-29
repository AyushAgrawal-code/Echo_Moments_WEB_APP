from django.contrib import admin
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase
from io import BytesIO, StringIO
from zipfile import ZipFile
from PIL import Image, ImageDraw, ImageFilter
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from .management.commands.process_upload_queue import Command as ProcessUploadQueueCommand
from .management.commands.process_face_index_queue import Command as ProcessFaceIndexQueueCommand
from .face_matching import (
    FaceEnrollmentError,
    FaceMatchingUnavailable,
    MAX_IMAGE_PIXELS,
    decrypt_embedding,
    extract_enrollment_embedding,
    extract_face_embeddings,
    similarity,
)
from .admin import EventAdminForm
from .models import Event, EventMember, FaceIndexJob, FaceMatch, Photo, UploadJob


class EventWorkflowTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="host@example.com", password="Test-pass-123")
        self.guest = User.objects.create_user(username="guest@example.com", password="Test-pass-123")
        self.other = User.objects.create_user(username="other@example.com", password="Test-pass-123")
        self.event = Event.objects.create(created_by=self.host, event_name="Test event", event_date="2026-11-01")
        EventMember.objects.create(user=self.host, event=self.event, role="host")
        self.upload_url = reverse("events:upload_photo", args=[self.event.event_code])

    def tearDown(self):
        for event in Event.objects.all():
            if event.cover_photo:
                event.cover_photo.delete(save=False)
        for job in UploadJob.objects.all():
            if job.source_file:
                job.source_file.delete(save=False)
        for photo in Photo.objects.all():
            if photo.image:
                photo.image.delete(save=False)

    def test_event_creation_creates_host_membership(self):
        self.client.force_login(self.host)
        response = self.client.post(reverse("events:create_event"), {
            "event_name": "Created event", "event_date": "2026-12-01",
            "privacy": "public", "theme_color": "emerald", "allow_upload": "on",
        })
        self.assertEqual(response.status_code, 201)
        event = Event.objects.get(event_code=response.json()["event_code"])
        self.assertTrue(EventMember.objects.filter(event=event, user=self.host, role="host", is_active=True).exists())

    def test_creation_ui_removes_tag_and_comment_permissions_and_saves_remaining_settings(self):
        self.client.force_login(self.host)
        page = self.client.get(reverse("events:create_event"))
        self.assertNotContains(page, 'name="allow_tag"')
        self.assertNotContains(page, 'name="allow_comment"')
        response = self.client.post(reverse("events:create_event"), {
            "event_name": "Private celebration",
            "event_date": "2026-12-01",
            "privacy": "private",
            "theme_color": "gold",
        })
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["privacy"], "private")
        self.assertIn("/events/invite/", payload["join_url"])
        event = Event.objects.get(event_code=payload["event_code"])
        self.assertEqual(event.privacy, "private")
        self.assertEqual(event.theme_color, "gold")
        self.assertFalse(event.allow_upload)
        self.assertFalse(event.allow_download)
        self.assertFalse(event.allow_tag)
        self.assertFalse(event.allow_comment)

    def test_private_invitation_link_grants_membership_once_and_code_does_not(self):
        self.event.privacy = "private"
        self.event.save(update_fields=["privacy"])
        invite_url = reverse("events:accept_event_invite", args=[self.event.invite_token])
        self.client.force_login(self.guest)
        self.client.post(reverse("events:join_event"), {"event_code": self.event.event_code})
        self.assertFalse(EventMember.objects.filter(event=self.event, user=self.guest).exists())
        first = self.client.get(invite_url)
        second = self.client.get(invite_url)
        self.assertRedirects(first, reverse("events:event_detail", args=[self.event.event_code]))
        self.assertRedirects(second, reverse("events:event_detail", args=[self.event.event_code]))
        member = EventMember.objects.get(event=self.event, user=self.guest)
        self.assertTrue(member.is_active)
        self.assertEqual(member.join_method, "invite")

    def test_invitation_link_cannot_join_ended_event_or_hidden_event(self):
        self.event.privacy = "private"
        self.event.save(update_fields=["privacy"])
        invite_url = reverse("events:accept_event_invite", args=[self.event.invite_token])
        self.client.force_login(self.guest)
        self.event.is_active = False
        self.event.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(invite_url).status_code, 410)
        self.assertFalse(EventMember.objects.filter(event=self.event, user=self.guest).exists())
        self.event.is_active = True
        self.event.privacy = "hidden"
        self.event.save(update_fields=["is_active", "privacy"])
        self.assertEqual(self.client.get(invite_url).status_code, 404)

    def test_event_cover_is_rendered_through_member_checked_private_endpoint(self):
        image_buffer = BytesIO()
        Image.new("RGB", (4, 3), color="orange").save(image_buffer, format="PNG")
        self.event.cover_photo.save(
            "cover.png",
            SimpleUploadedFile("cover.png", image_buffer.getvalue(), content_type="image/png"),
            save=True,
        )
        cover_url = reverse("events:view_event_cover", args=[self.event.event_code])
        self.client.force_login(self.host)
        host_response = self.client.get(cover_url)
        self.assertEqual(host_response.status_code, 200)
        self.assertEqual(host_response["Content-Type"], "image/png")
        self.assertEqual(host_response["Cache-Control"], "private, no-store")
        host_response.close()
        detail = self.client.get(reverse("events:event_detail", args=[self.event.event_code]))
        self.assertContains(detail, cover_url)

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(cover_url).status_code, 403)
        EventMember.objects.create(user=self.guest, event=self.event, role="guest")
        self.client.force_login(self.guest)
        guest_response = self.client.get(cover_url)
        self.assertEqual(guest_response.status_code, 200)
        guest_response.close()

    def test_event_cover_rejects_documents_programs_audio_and_video(self):
        self.client.force_login(self.host)
        invalid_files = (
            ("cover.pdf", b"%PDF-1.7\nnot-an-image", "application/pdf"),
            ("cover.exe", b"MZ\x90\x00not-an-image", "application/octet-stream"),
            ("cover.mp3", b"ID3\x04\x00\x00not-an-image", "audio/mpeg"),
            ("cover.mp4", b"\x00\x00\x00\x18ftypmp42not-an-image", "video/mp4"),
        )
        for filename, content, content_type in invalid_files:
            with self.subTest(filename=filename):
                response = self.client.post(reverse("events:create_event"), {
                    "event_name": "Cover validation",
                    "event_date": "2026-12-01",
                    "cover_photo": SimpleUploadedFile(filename, content, content_type=content_type),
                })
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Event.objects.filter(event_name="Cover validation").count(), 0)

    def test_admin_event_form_rejects_non_image_cover_files(self):
        invalid_files = (
            ("cover.pdf", b"%PDF-1.7\nnot-an-image", "application/pdf"),
            ("cover.exe", b"MZ\x90\x00not-an-image", "application/octet-stream"),
            ("cover.mp3", b"ID3\x04\x00\x00not-an-image", "audio/mpeg"),
            ("cover.mp4", b"\x00\x00\x00\x18ftypmp42not-an-image", "video/mp4"),
        )
        for filename, content, content_type in invalid_files:
            with self.subTest(filename=filename):
                form = EventAdminForm(
                    data={
                        "event_name": "Admin cover validation",
                        "event_date": "2026-12-01",
                        "privacy": "public",
                        "theme_color": "emerald",
                        "created_by": self.host.pk,
                    },
                    files={"cover_photo": SimpleUploadedFile(filename, content, content_type=content_type)},
                    instance=self.event,
                )
                self.assertIn("cover_photo", form.errors)

    def test_public_event_join_creates_guest_membership_and_is_idempotent(self):
        self.client.force_login(self.guest)
        for _ in range(2):
            response = self.client.post(reverse("events:join_event"), {"event_code": self.event.event_code})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(EventMember.objects.filter(event=self.event, user=self.guest).count(), 1)
        self.assertEqual(EventMember.objects.get(event=self.event, user=self.guest).role, "guest")

    def test_guest_sees_guest_dashboard_and_unrelated_user_is_denied(self):
        EventMember.objects.create(user=self.guest, event=self.event, role="guest")
        self.client.force_login(self.guest)
        response = self.client.get(reverse("events:event_detail", args=[self.event.event_code]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/guest_event.html")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("events:event_detail", args=[self.event.event_code])).status_code, 403)

    def test_shared_album_page_size_defaults_to_20_and_allows_30_or_50(self):
        Photo.objects.bulk_create([
            Photo(event=self.event, uploaded_by=self.host, image=f"event_photos/photo-{number}.png")
            for number in range(51)
        ])
        self.client.force_login(self.host)

        default_page = self.client.get(reverse("events:event_detail", args=[self.event.event_code]))
        self.assertEqual(default_page.context["photo_page"].paginator.per_page, 20)
        self.assertEqual(len(default_page.context["photos"]), 20)
        self.assertContains(default_page, 'name="page_size"')
        self.assertContains(default_page, "30")
        self.assertContains(default_page, "50")

        for requested_size in (30, 50):
            selected_page = self.client.get(
                reverse("events:event_detail", args=[self.event.event_code]),
                {"page_size": requested_size},
            )
            self.assertEqual(selected_page.context["photo_page"].paginator.per_page, requested_size)
            self.assertEqual(len(selected_page.context["photos"]), requested_size)
        self.assertContains(selected_page, 'href="?page=2&page_size=50#album"')

        invalid_size = self.client.get(
            reverse("events:event_detail", args=[self.event.event_code]), {"page_size": 1000}
        )
        self.assertEqual(invalid_size.context["photo_page"].paginator.per_page, 20)

    def test_non_images_corrupt_images_and_appended_program_payloads_are_rejected(self):
        EventMember.objects.create(user=self.guest, event=self.event, role="guest")
        self.client.force_login(self.guest)
        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), color="blue").save(image_buffer, format="PNG")
        valid_png = image_buffer.getvalue()
        invalid_uploads = (
            ("program.png", b"MZ\x90\x00not-a-photo", "image/png"),
            ("program.exe", b"MZ\x90\x00not-a-photo", "application/octet-stream"),
            ("document.pdf", b"%PDF-1.7\nnot-a-photo", "application/pdf"),
            ("recording.mp3", b"ID3\x04\x00\x00not-a-photo", "audio/mpeg"),
            ("clip.mp4", b"\x00\x00\x00\x18ftypmp42not-a-photo", "video/mp4"),
            ("truncated.png", valid_png[:-12], "image/png"),
            ("photo-with-payload.png", valid_png + b"MZ executable payload", "image/png"),
        )

        for filename, content, content_type in invalid_uploads:
            with self.subTest(filename=filename):
                response = self.client.post(self.upload_url, {
                    "images": SimpleUploadedFile(filename, content, content_type=content_type)
                })
                self.assertEqual(response.status_code, 400)

        self.assertEqual(UploadJob.objects.filter(event=self.event).count(), 0)

    def test_host_member_controls_are_paginated_without_capping_membership(self):
        viewers = [User(username=f"viewer-{index}@example.com") for index in range(51)]
        User.objects.bulk_create(viewers)
        EventMember.objects.bulk_create([
            EventMember(user=user, event=self.event, role="guest")
            for user in User.objects.filter(username__startswith="viewer-")
        ])
        self.client.force_login(self.host)

        first_page = self.client.get(reverse("events:event_detail", args=[self.event.event_code]))
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.context["member_page"].paginator.count, 52)
        self.assertEqual(len(first_page.context["members"]), 50)

        second_page = self.client.get(
            reverse("events:event_detail", args=[self.event.event_code]), {"members_page": 2}
        )
        self.assertEqual(len(second_page.context["members"]), 2)

    def test_host_and_guest_photo_caps_reserve_queued_uploads(self):
        self.event.max_photo_count = 5
        self.event.host_photo_limit = 1
        self.event.guest_photo_pool_limit = 2
        self.event.member_photo_limit_enabled = True
        self.event.default_member_photo_limit = 1
        self.event.save()

        def upload_as(user, filename):
            image_buffer = BytesIO()
            Image.new("RGB", (2, 2), color="white").save(image_buffer, format="PNG")
            self.client.force_login(user)
            return self.client.post(self.upload_url, {
                "images": SimpleUploadedFile(filename, image_buffer.getvalue(), content_type="image/png")
            })

        self.assertEqual(upload_as(self.host, "host-one.png").status_code, 202)
        self.assertEqual(upload_as(self.host, "host-two.png").status_code, 409)

        EventMember.objects.create(user=self.guest, event=self.event, role="guest")
        self.assertEqual(upload_as(self.guest, "guest-one.png").status_code, 202)
        self.assertEqual(upload_as(self.guest, "guest-two.png").status_code, 409)

        second_guest = User.objects.create_user(username="second-guest@example.com")
        EventMember.objects.create(user=second_guest, event=self.event, role="guest")
        self.assertEqual(upload_as(second_guest, "second-guest.png").status_code, 202)

        third_guest = User.objects.create_user(username="third-guest@example.com")
        EventMember.objects.create(user=third_guest, event=self.event, role="guest")
        self.assertEqual(upload_as(third_guest, "guest-pool-full.png").status_code, 409)

    def test_oversized_event_photo_is_rejected_before_staging(self):
        EventMember.objects.create(user=self.guest, event=self.event, role="guest")
        self.client.force_login(self.guest)
        with patch("events.views.Image.open") as open_image:
            image = open_image.return_value.__enter__.return_value
            image.format = "PNG"
            image.width = MAX_IMAGE_PIXELS + 1
            image.height = 1
            response = self.client.post(self.upload_url, {
                "images": SimpleUploadedFile("huge.png", b"image-header", content_type="image/png")
            })
        self.assertEqual(response.status_code, 413)
        self.assertEqual(UploadJob.objects.filter(event=self.event).count(), 0)
        image.verify.assert_not_called()

    def test_shared_album_remains_available_after_event_ends_but_stays_private(self):
        membership = EventMember.objects.create(user=self.guest, event=self.event, role="guest")
        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), color="white").save(image_buffer, format="PNG")
        photo = Photo.objects.create(
            event=self.event,
            uploaded_by=self.guest,
            image=SimpleUploadedFile("shared.png", image_buffer.getvalue(), content_type="image/png"),
        )
        self.event.is_active = False
        self.event.save(update_fields=["is_active"])

        self.client.force_login(self.guest)
        album = self.client.get(reverse("events:event_detail", args=[self.event.event_code]))
        self.assertEqual(album.status_code, 200)
        self.assertEqual(album.context["membership"].pk, membership.pk)
        image_response = self.client.get(reverse("events:view_photo", args=[self.event.event_code, photo.pk]))
        self.assertEqual(image_response.status_code, 200)
        image_response.close()

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("events:event_detail", args=[self.event.event_code])).status_code, 410)
        self.assertEqual(self.client.get(reverse("events:view_photo", args=[self.event.event_code, photo.pk])).status_code, 403)

    def test_upload_extension_and_photo_responses_use_verified_image_format(self):
        EventMember.objects.create(user=self.guest, event=self.event, role="guest")
        self.client.force_login(self.guest)
        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), color="green").save(image_buffer, format="PNG")

        response = self.client.post(self.upload_url, {
            "images": SimpleUploadedFile("<script>photo.html", image_buffer.getvalue(), content_type="text/html")
        })
        self.assertEqual(response.status_code, 202)
        job = UploadJob.objects.get(idempotency_key=response.json()["job_id"])
        self.assertTrue(job.original_name.endswith(".png"))
        self.assertNotIn("<", job.original_name)

        call_command("process_upload_queue", once=True)
        photo = Photo.objects.get(event=self.event, uploaded_by=self.guest)
        self.assertTrue(photo.image.name.endswith(".png"))

        # Simulate an older object whose stored suffix disagrees with its bytes.
        storage = photo.image.storage
        original_storage_name = photo.image.name
        with photo.image.open("rb") as source:
            png_bytes = source.read()
        html_storage_name = storage.save(
            f"event_photos/legacy-photo-{photo.pk}.html", ContentFile(png_bytes)
        )
        photo.image.name = html_storage_name
        photo.save(update_fields=["image"])
        storage.delete(original_storage_name)

        view_response = self.client.get(reverse("events:view_photo", args=[self.event.event_code, photo.pk]))
        self.assertEqual(view_response.status_code, 200)
        self.assertEqual(view_response["Content-Type"], "image/png")
        self.assertIn(f'filename="photo-{photo.pk}.png"', view_response["Content-Disposition"])
        view_response.close()

        download_response = self.client.get(reverse("events:download_photo", args=[self.event.event_code, photo.pk]))
        self.assertEqual(download_response["Content-Type"], "image/png")
        self.assertIn(f'filename="photo-{photo.pk}.png"', download_response["Content-Disposition"])
        download_response.close()

        membership = EventMember.objects.get(user=self.guest, event=self.event)
        membership.face_consent_at = timezone.now()
        membership.face_embedding_ciphertext = "encrypted-test-template"
        membership.save(update_fields=["face_consent_at", "face_embedding_ciphertext"])
        FaceMatch.objects.create(photo=photo, user=self.guest, similarity=0.99)
        zip_response = self.client.get(reverse("events:download_my_photos", args=[self.event.event_code]))
        self.assertEqual(zip_response.status_code, 200)
        with ZipFile(BytesIO(b"".join(zip_response.streaming_content))) as archive:
            self.assertEqual(archive.namelist(), [f"photo-{photo.pk}.png"])
        zip_response.close()

    def test_private_event_rejects_code_join(self):
        self.event.privacy = "private"
        self.event.save(update_fields=["privacy"])
        self.client.force_login(self.guest)
        self.client.post(reverse("events:join_event"), {"event_code": self.event.event_code})
        self.assertFalse(EventMember.objects.filter(event=self.event, user=self.guest).exists())

    def test_unrelated_user_cannot_upload(self):
        self.client.force_login(self.other)
        response = self.client.post(self.upload_url, {"image": SimpleUploadedFile("x.png", b"bad", content_type="image/png")})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Photo.objects.filter(event=self.event).count(), 0)

    def test_guest_cannot_change_settings_or_end_event(self):
        EventMember.objects.create(user=self.guest, event=self.event, role="guest")
        self.client.force_login(self.guest)
        self.assertEqual(self.client.post(reverse("events:toggle_upload", args=[self.event.event_code])).status_code, 403)
        self.assertEqual(self.client.post(reverse("events:end_event", args=[self.event.event_code])).status_code, 403)
        self.event.refresh_from_db()
        self.assertTrue(self.event.is_active)
        self.assertTrue(self.event.allow_upload)

    def test_management_endpoints_reject_get(self):
        self.client.force_login(self.host)
        self.assertEqual(self.client.get(reverse("events:end_event", args=[self.event.event_code])).status_code, 405)

    def test_member_uploads_persist_when_enabled(self):
        EventMember.objects.create(user=self.guest, event=self.event, role="guest")
        self.client.force_login(self.guest)
        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), color="white").save(image_buffer, format="PNG")
        response = self.client.post(self.upload_url, {"images": SimpleUploadedFile("one.png", image_buffer.getvalue(), content_type="image/png")})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], UploadJob.Status.QUEUED)
        self.assertEqual(Photo.objects.filter(event=self.event).count(), 0)

        call_command("process_upload_queue", once=True)
        job = UploadJob.objects.get(idempotency_key=response.json()["job_id"])
        self.assertEqual(job.status, UploadJob.Status.COMPLETE)
        photo = Photo.objects.get(event=self.event)
        self.assertEqual(photo.uploaded_by, self.guest)
        photo.image.delete(save=False)
        job.source_file.delete(save=False)

    def test_failed_photo_retries_automatically_then_requeues_without_reupload(self):
        EventMember.objects.create(user=self.guest, event=self.event, role="guest")
        self.client.force_login(self.guest)
        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), color="white").save(image_buffer, format="PNG")
        response = self.client.post(self.upload_url, {
            "images": SimpleUploadedFile("retry-me.png", image_buffer.getvalue(), content_type="image/png")
        })
        self.assertEqual(response.status_code, 202)
        job = UploadJob.objects.get(idempotency_key=response.json()["job_id"])
        photo_storage = Photo._meta.get_field("image").storage

        for expected_attempt in range(1, job.max_attempts + 1):
            UploadJob.objects.filter(pk=job.pk).update(available_at=timezone.now())
            with patch.object(photo_storage, "save", side_effect=OSError("temporary storage failure")):
                call_command("process_upload_queue", once=True, stderr=StringIO())
            job.refresh_from_db()
            self.assertEqual(job.attempts, expected_attempt)
            expected_status = (
                UploadJob.Status.FAILED
                if expected_attempt == job.max_attempts
                else UploadJob.Status.QUEUED
            )
            self.assertEqual(job.status, expected_status)

        staged_name = job.source_file.name
        self.assertTrue(staged_name)
        self.assertTrue(job.source_file.storage.exists(staged_name))

        retry = self.client.post(reverse(
            "events:retry_upload_job", args=[self.event.event_code, job.idempotency_key]
        ))
        self.assertEqual(retry.status_code, 202)
        self.assertEqual(retry.json()["status"], UploadJob.Status.QUEUED)
        job.refresh_from_db()
        self.assertEqual(job.status, UploadJob.Status.QUEUED)
        self.assertEqual(job.attempts, 0)
        self.assertTrue(job.source_file.storage.exists(staged_name))

        UploadJob.objects.filter(pk=job.pk).update(available_at=timezone.now())
        call_command("process_upload_queue", once=True)
        job.refresh_from_db()
        self.assertEqual(job.status, UploadJob.Status.COMPLETE)
        self.assertEqual(Photo.objects.filter(event=self.event, uploaded_by=self.guest).count(), 1)


class FaceMatchingWorkflowTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="face-host@example.com")
        self.member = User.objects.create_user(username="face-member@example.com")
        self.unenrolled = User.objects.create_user(username="face-unenrolled@example.com")
        self.event = Event.objects.create(created_by=self.host, event_name="Face event", event_date="2026-11-01")
        EventMember.objects.create(user=self.host, event=self.event, role="host")
        self.member_link = EventMember.objects.create(user=self.member, event=self.event, role="guest")
        EventMember.objects.create(user=self.unenrolled, event=self.event, role="guest")

    def tearDown(self):
        for photo in Photo.objects.all():
            if photo.image:
                photo.image.delete(save=False)

    def make_photo(self):
        image_buffer = BytesIO()
        Image.new("RGB", (100, 100), color="white").save(image_buffer, format="PNG")
        return Photo.objects.create(
            event=self.event,
            uploaded_by=self.host,
            image=SimpleUploadedFile("face-event.png", image_buffer.getvalue(), content_type="image/png"),
        )

    def test_oversized_face_image_is_rejected_before_loading_opencv_models(self):
        with patch("PIL.Image.open") as open_image:
            image = open_image.return_value.__enter__.return_value
            image.size = (MAX_IMAGE_PIXELS + 1, 1)
            with patch("events.face_matching._models") as models:
                with self.assertRaises(FaceEnrollmentError):
                    extract_face_embeddings(b"image-header")
                models.assert_not_called()

    def test_personal_album_offers_upload_and_camera_selfie_options(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("events:my_photos", args=[self.event.event_code]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="chooseSelfieUpload"')
        self.assertContains(response, 'id="chooseSelfieCamera"')
        self.assertContains(response, 'capture="user"')
        self.assertContains(response, "selfie_capture.")

    def test_synthetic_face_can_enroll_and_match_an_event_photo_end_to_end(self):
        image = Image.new("RGB", (512, 512), "#c8d6e5")
        draw = ImageDraw.Draw(image)
        draw.ellipse((85, 60, 427, 490), fill="#2b2928")
        draw.ellipse((133, 79, 379, 392), fill="#d9a880")
        draw.polygon(
            [(133, 174), (141, 101), (206, 67), (312, 74), (379, 119), (370, 170), (322, 127), (271, 114), (203, 123)],
            fill="#292726",
        )
        draw.ellipse((164, 194, 228, 226), fill="#f0e4d8")
        draw.ellipse((281, 194, 345, 226), fill="#f0e4d8")
        draw.ellipse((185, 202, 211, 226), fill="#45342c")
        draw.ellipse((304, 202, 330, 226), fill="#45342c")
        draw.ellipse((194, 207, 203, 217), fill="#171717")
        draw.ellipse((313, 207, 322, 217), fill="#171717")
        draw.arc((160, 176, 230, 211), 190, 350, fill="#3a2a22", width=9)
        draw.arc((278, 176, 348, 211), 190, 350, fill="#3a2a22", width=9)
        draw.polygon([(250, 208), (232, 278), (248, 288), (267, 278)], fill="#be8865")
        draw.ellipse((232, 274, 257, 286), fill="#bd8265")
        draw.arc((211, 290, 299, 349), 10, 170, fill="#713b3a", width=10)
        draw.line((174, 385, 165, 500), fill="#d9a880", width=25)
        draw.line((340, 385, 349, 500), fill="#d9a880", width=25)
        image_buffer = BytesIO()
        image.filter(ImageFilter.GaussianBlur(0.4)).save(image_buffer, format="PNG")
        image_bytes = image_buffer.getvalue()

        try:
            embeddings = extract_face_embeddings(image_bytes)
        except FaceMatchingUnavailable as exc:
            self.skipTest(f"OpenCV models are unavailable in this test environment: {exc}")
        self.assertEqual(len(embeddings), 1)
        self.assertEqual(len(embeddings[0]), 128)
        expected_enrollment_embedding = extract_enrollment_embedding(image_bytes)

        self.client.force_login(self.member)
        response = self.client.post(
            reverse("events:enroll_face", args=[self.event.event_code]),
            {
                "face_consent": "on",
                "selfie": SimpleUploadedFile("synthetic-face.png", image_bytes, content_type="image/png"),
            },
        )

        self.assertRedirects(response, reverse("events:my_photos", args=[self.event.event_code]))
        self.member_link.refresh_from_db()
        self.assertTrue(self.member_link.face_consent_at)
        self.assertTrue(self.member_link.face_embedding_ciphertext)
        recovered_embedding = decrypt_embedding(self.member_link.face_embedding_ciphertext)
        self.assertAlmostEqual(similarity(expected_enrollment_embedding, recovered_embedding), 1.0, places=5)

        photo = Photo.objects.create(
            event=self.event,
            uploaded_by=self.host,
            image=SimpleUploadedFile("synthetic-event.png", image_bytes, content_type="image/png"),
        )
        FaceIndexJob.objects.create(photo=photo, available_at=timezone.now())
        ProcessFaceIndexQueueCommand().handle(
            once=True, poll_seconds=0.2, stale_after_seconds=300, retry_failed=False
        )

        match = FaceMatch.objects.get(photo=photo, user=self.member)
        self.assertGreaterEqual(match.similarity, 0.5)
        self.assertLessEqual(match.similarity, 1.0)
        self.assertFalse(FaceMatch.objects.filter(photo=photo, user__in=[self.host, self.unenrolled]).exists())
        self.assertEqual(Photo.objects.filter(event=self.event).count(), 1)
        self.assertIn("synthetic-event.png", photo.image.name)
        self.assertNotIn("synthetic-face.png", photo.image.name)

    def test_unavailable_face_runtime_does_not_store_or_request_a_selfie_again(self):
        image_buffer = BytesIO()
        Image.new("RGB", (100, 100), color="white").save(image_buffer, format="PNG")
        self.client.force_login(self.member)
        with patch(
            "events.views.extract_enrollment_embedding",
            side_effect=FaceMatchingUnavailable("Install opencv-contrib-python-headless"),
        ):
            response = self.client.post(
                reverse("events:enroll_face", args=[self.event.event_code]),
                {
                    "face_consent": "on",
                    "selfie": SimpleUploadedFile("selfie.png", image_buffer.getvalue(), content_type="image/png"),
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "Your selfie was not saved.", status_code=503)
        self.assertNotContains(response, "Install opencv-contrib-python-headless", status_code=503)
        self.assertNotContains(response, "Find my photos", status_code=503)
        self.member_link.refresh_from_db()
        self.assertFalse(self.member_link.face_embedding_ciphertext)
        self.assertIsNone(self.member_link.face_consent_at)

    def test_face_index_worker_matches_only_members_who_opted_in(self):
        self.member_link.face_consent_at = timezone.now()
        self.member_link.face_embedding_ciphertext = "encrypted-template"
        self.member_link.face_model_version = "test-model"
        self.member_link.save(update_fields=["face_consent_at", "face_embedding_ciphertext", "face_model_version"])
        photo = self.make_photo()
        FaceIndexJob.objects.create(photo=photo, available_at=timezone.now())

        with (
            patch("events.management.commands.process_face_index_queue.model_version", return_value="test-model"),
            patch("events.management.commands.process_face_index_queue.decrypt_embedding", return_value=[1.0]),
            patch("events.management.commands.process_face_index_queue.extract_face_embeddings", return_value=[[1.0]]),
            patch("events.management.commands.process_face_index_queue.similarity", return_value=0.99),
        ):
            ProcessFaceIndexQueueCommand().handle(
                once=True, poll_seconds=0.2, stale_after_seconds=300, retry_failed=False
            )

        self.assertTrue(FaceMatch.objects.filter(photo=photo, user=self.member).exists())
        self.assertFalse(FaceMatch.objects.filter(photo=photo, user=self.unenrolled).exists())

    def test_personal_album_is_private_opt_in_gated_and_revocable(self):
        photo = self.make_photo()
        FaceMatch.objects.create(photo=photo, user=self.member, similarity=0.99)
        FaceMatch.objects.create(photo=photo, user=self.unenrolled, similarity=0.98)
        self.member_link.face_consent_at = timezone.now()
        self.member_link.face_embedding_ciphertext = "encrypted-template"
        self.member_link.face_model_version = "test-model"
        self.member_link.save(update_fields=["face_consent_at", "face_embedding_ciphertext", "face_model_version"])

        self.client.force_login(self.member)
        response = self.client.get(reverse("events:my_photos", args=[self.event.event_code]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["matches_count"], 1)
        self.assertContains(response, "Update your selfie")
        self.assertContains(response, 'name="selfie"')
        self.assertEqual(response.context["match_page"].paginator.per_page, 20)
        paged_response = self.client.get(
            reverse("events:my_photos", args=[self.event.event_code]), {"page_size": 50}
        )
        self.assertEqual(paged_response.context["match_page"].paginator.per_page, 50)
        self.assertContains(paged_response, 'name="page_size"')
        self.client.force_login(self.unenrolled)
        unenrolled_album = self.client.get(reverse("events:my_photos", args=[self.event.event_code]))
        self.assertEqual(unenrolled_album.status_code, 200)
        self.assertEqual(unenrolled_album.context["matches_count"], 0)
        self.assertEqual(self.client.post(
            reverse("events:download_my_photos", args=[self.event.event_code]),
            {"photo_ids": str(photo.pk)},
        ).status_code, 403)

        self.client.force_login(self.member)
        revoke = self.client.post(reverse("events:revoke_face_enrollment", args=[self.event.event_code]))
        self.assertEqual(revoke.status_code, 302)
        self.member_link.refresh_from_db()
        self.assertEqual(self.member_link.face_embedding_ciphertext, "")
        self.assertIsNone(self.member_link.face_consent_at)
        self.assertFalse(FaceMatch.objects.filter(user=self.member, photo__event=self.event).exists())

class UploadQueueSchedulingTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="queue-host@example.com")
        self.guest = User.objects.create_user(username="queue-guest@example.com")
        self.event = Event.objects.create(created_by=self.host, event_name="Queue event", event_date="2026-11-01")

    def make_job(self, uploader, priority):
        return UploadJob.objects.create(
            event=self.event,
            uploader=uploader,
            original_name=f"{uploader.username}-{UploadJob.objects.count()}.png",
            priority=priority,
            available_at=timezone.now(),
        )

    def test_host_is_default_and_aged_guest_turn_is_paced(self):
        host_first = self.make_job(self.host, priority=100)
        guest_first = self.make_job(self.guest, priority=0)
        scheduler = ProcessUploadQueueCommand()

        claimed = scheduler._claim_next_job(guest_wait_seconds=30)
        self.assertEqual(claimed.pk, host_first.pk)

        UploadJob.objects.filter(pk=guest_first.pk).update(
            created_at=timezone.now() - timedelta(seconds=31)
        )
        claimed = scheduler._claim_next_job(guest_wait_seconds=30)
        self.assertEqual(claimed.pk, guest_first.pk)

        host_next = self.make_job(self.host, priority=100)
        guest_next = self.make_job(self.guest, priority=0)
        UploadJob.objects.filter(pk=guest_next.pk).update(
            created_at=timezone.now() - timedelta(seconds=31)
        )
        claimed = scheduler._claim_next_job(guest_wait_seconds=30)
        self.assertEqual(claimed.pk, host_next.pk)


class AdminPortalTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="Admin-pass-123",
        )

    def test_staff_can_open_event_member_and_queue_admin_pages(self):
        models = (Event, EventMember, Photo, UploadJob, FaceIndexJob, User)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
        for model in models:
            route = f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist"
            with self.subTest(model=model.__name__):
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)

    def test_admin_does_not_expose_raw_face_templates_or_private_file_fields(self):
        member_admin = admin.site._registry[EventMember]
        photo_admin = admin.site._registry[Photo]
        upload_admin = admin.site._registry[UploadJob]

        self.assertNotIn("face_embedding_ciphertext", member_admin.fields)
        self.assertIn("face_consent_at", member_admin.readonly_fields)
        self.assertNotIn("image", photo_admin.fields)
        self.assertFalse(photo_admin.has_add_permission(None))
        self.assertNotIn("source_file", upload_admin.fields)
        self.assertIn("staged_filename", upload_admin.readonly_fields)
        self.assertFalse(upload_admin.has_add_permission(None))

