from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from io import BytesIO
from PIL import Image
from django.urls import reverse

from .models import Event, EventMember, Photo


class EventWorkflowTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="host@example.com", password="Test-pass-123")
        self.guest = User.objects.create_user(username="guest@example.com", password="Test-pass-123")
        self.other = User.objects.create_user(username="other@example.com", password="Test-pass-123")
        self.event = Event.objects.create(created_by=self.host, event_name="Test event", event_date="2026-11-01")
        EventMember.objects.create(user=self.host, event=self.event, role="host")
        self.upload_url = reverse("events:upload_photo", args=[self.event.event_code])

    def test_event_creation_creates_host_membership(self):
        self.client.force_login(self.host)
        response = self.client.post(reverse("events:create_event"), {
            "event_name": "Created event", "event_date": "2026-12-01",
            "privacy": "public", "theme_color": "emerald", "allow_upload": "on",
        })
        self.assertEqual(response.status_code, 201)
        event = Event.objects.get(event_code=response.json()["event_code"])
        self.assertTrue(EventMember.objects.filter(event=event, user=self.host, role="host", is_active=True).exists())

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

    def test_member_uploads_persist_when_enabled(self):
        EventMember.objects.create(user=self.guest, event=self.event, role="guest")
        self.client.force_login(self.guest)
        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), color="white").save(image_buffer, format="PNG")
        response = self.client.post(self.upload_url, {"images": SimpleUploadedFile("one.png", image_buffer.getvalue(), content_type="image/png")})
        self.assertEqual(response.status_code, 201)
        photo = Photo.objects.get(event=self.event)
        self.assertEqual(photo.uploaded_by, self.guest)
        photo.image.delete(save=False)

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

