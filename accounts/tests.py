from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from .admin import UserProfileAdminForm


class ProfileUpdateTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username="profile-user@example.com",
			email="profile-user@example.com",
			password="test-password-123",
		)
		self.client.force_login(self.user)

	def test_profile_form_updates_last_name_without_other_profile_fields(self):
		response = self.client.post(
			reverse("accounts:profile"),
			{
				"form_type": "profile",
				"first_name": self.user.first_name,
				"last_name": "UpdatedLastName",
				"email": self.user.email,
			},
		)

		self.assertRedirects(response, reverse("accounts:profile"))
		self.user.refresh_from_db()
		self.assertEqual(self.user.last_name, "UpdatedLastName")

	def test_profile_photo_rejects_document_program_audio_and_video_files(self):
		invalid_files = (
			("profile.pdf", b"%PDF-1.7\nnot-an-image", "application/pdf"),
			("profile.exe", b"MZ\x90\x00not-an-image", "application/octet-stream"),
			("profile.mp3", b"ID3\x04\x00\x00not-an-image", "audio/mpeg"),
			("profile.mp4", b"\x00\x00\x00\x18ftypmp42not-an-image", "video/mp4"),
		)
		for filename, content, content_type in invalid_files:
			with self.subTest(filename=filename):
				response = self.client.post(
					reverse("accounts:profile"),
					{
						"form_type": "avatar",
						"profile_pic": SimpleUploadedFile(filename, content, content_type=content_type),
					},
				)
				self.assertEqual(response.status_code, 200)
		self.assertFalse(self.user.profile.profile_pic)

	def test_admin_profile_form_rejects_non_image_files(self):
		invalid_files = (
			("profile.pdf", b"%PDF-1.7\nnot-an-image", "application/pdf"),
			("profile.exe", b"MZ\x90\x00not-an-image", "application/octet-stream"),
			("profile.mp3", b"ID3\x04\x00\x00not-an-image", "audio/mpeg"),
			("profile.mp4", b"\x00\x00\x00\x18ftypmp42not-an-image", "video/mp4"),
		)
		for filename, content, content_type in invalid_files:
			with self.subTest(filename=filename):
				form = UserProfileAdminForm(
					data={"user": self.user.pk},
					files={"profile_pic": SimpleUploadedFile(filename, content, content_type=content_type)},
					instance=self.user.profile,
				)
				self.assertIn("profile_pic", form.errors)
