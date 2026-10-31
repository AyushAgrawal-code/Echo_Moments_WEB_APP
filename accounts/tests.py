from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
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

	def test_profile_page_offers_whatsapp_style_photo_crop_controls(self):
		response = self.client.get(reverse("accounts:profile"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'id="avatarCropStage"')
		self.assertContains(response, 'id="avatarCropZoom"')
		self.assertContains(response, 'id="saveAvatarCrop"')
		self.assertContains(response, "Change / crop photo")
		self.assertContains(response, 'id="cancelAvatarCrop"')
		self.assertContains(response, "profile_avatar_crop.")
		self.assertNotContains(response, "```")

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


class AccountAuthenticationTests(TestCase):
	def test_signup_enforces_password_validators_and_rejects_duplicates(self):
		weak_response = self.client.post(reverse("accounts:auth"), {
			"form_type": "signup",
			"signup-name": "QA Account",
			"signup-email": "weak-password@example.test",
			"signup-password": "123",
		})
		self.assertRedirects(weak_response, reverse("accounts:signup"))
		self.assertFalse(User.objects.filter(username="weak-password@example.test").exists())

		good_response = self.client.post(reverse("accounts:auth"), {
			"form_type": "signup",
			"signup-name": "QA Account",
			"signup-email": "qa-account@example.test",
			"signup-password": "Long-Unique-Passphrase-947!",
		})
		self.assertRedirects(good_response, reverse("accounts:login"))
		self.assertTrue(User.objects.filter(username="qa-account@example.test").exists())

		duplicate_response = self.client.post(reverse("accounts:auth"), {
			"form_type": "signup",
			"signup-name": "Duplicate",
			"signup-email": "QA-ACCOUNT@example.test",
			"signup-password": "Long-Unique-Passphrase-947!",
		})
		self.assertRedirects(duplicate_response, reverse("accounts:signup"))
		self.assertEqual(User.objects.filter(email__iexact="qa-account@example.test").count(), 1)

	def test_legacy_signup_endpoint_uses_the_same_password_validation(self):
		response = self.client.post(reverse("accounts:signup"), {
			"username": "QA Legacy",
			"email": "legacy-weak@example.test",
			"password": "123",
		})
		self.assertRedirects(response, reverse("accounts:signup"))
		self.assertFalse(User.objects.filter(email="legacy-weak@example.test").exists())

	def test_login_logout_and_dashboard_access_flow(self):
		user = User.objects.create_user(
			username="auth-flow@example.test",
			email="auth-flow@example.test",
			password="Long-Unique-Passphrase-947!",
		)
		login_page = self.client.get(reverse("accounts:login"))
		self.assertContains(login_page, reverse("accounts:password_reset"))
		self.assertNotContains(login_page, "social-button")
		self.assertContains(login_page, 'id="login-form"')

		response = self.client.post(reverse("accounts:auth"), {
			"form_type": "login",
			"login-email": user.email,
			"login-password": "Long-Unique-Passphrase-947!",
		})
		self.assertRedirects(response, reverse("accounts:dashboard"))
		dashboard = self.client.get(reverse("accounts:dashboard"))
		self.assertEqual(dashboard.status_code, 200)
		self.assertContains(dashboard, f'{reverse("accounts:dashboard")}#your-events')

		self.assertEqual(self.client.post(reverse("accounts:logout")).status_code, 302)
		self.assertEqual(self.client.get(reverse("accounts:dashboard")).status_code, 302)

	def test_signup_password_meter_is_bound_to_the_real_signup_form(self):
		page = self.client.get(reverse("accounts:signup"))
		self.assertContains(page, 'id="signup-form"')
		self.assertNotContains(page, "social-button")

	@override_settings(GOOGLE_LOGIN_ENABLED=False)
	def test_google_signin_is_hidden_until_credentials_are_configured(self):
		page = self.client.get(reverse("accounts:login"))
		self.assertNotContains(page, "Continue with Google")
		self.assertEqual(self.client.get("/accounts/google/login/").status_code, 200)

	@override_settings(GOOGLE_LOGIN_ENABLED=True)
	def test_google_signin_button_posts_to_google_provider(self):
		page = self.client.get(reverse("accounts:login"))
		self.assertContains(page, "Continue with Google")
		self.assertContains(page, 'action="/accounts/google/login/"')

	@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
	def test_password_reset_email_link_changes_password_end_to_end(self):
		user = User.objects.create_user(
			username="reset@example.test",
			email="reset@example.test",
			password="Old-Unique-Passphrase-943!",
		)
		response = self.client.post(reverse("accounts:password_reset"), {"email": user.email})
		self.assertRedirects(response, reverse("accounts:password_reset_done"))
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(self.client.get(reverse("accounts:password_reset_done")).status_code, 200)

		import re
		match = re.search(r"https?://[^/]+(/accounts/password-reset/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/)", mail.outbox[0].body)
		self.assertIsNotNone(match, mail.outbox[0].body)
		confirm_response = self.client.get(match.group(1))
		self.assertEqual(confirm_response.status_code, 302)
		confirm_page = self.client.get(confirm_response.url)
		self.assertContains(confirm_page, 'name="new_password1"')
		complete = self.client.post(confirm_response.url, {
			"new_password1": "New-Unique-Passphrase-643!",
			"new_password2": "New-Unique-Passphrase-643!",
		})
		self.assertRedirects(complete, reverse("accounts:password_reset_complete"))
		user.refresh_from_db()
		self.assertTrue(user.check_password("New-Unique-Passphrase-643!"))


class GoogleAuthAdapterTests(TestCase):
	def setUp(self):
		from django.test import RequestFactory
		from accounts.adapters import CustomSocialAccountAdapter
		self.factory = RequestFactory()
		self.adapter = CustomSocialAccountAdapter()

	def test_existing_user_with_same_email_is_auto_connected_and_password_retained(self):
		from allauth.socialaccount.models import SocialAccount, SocialLogin
		from allauth.account.models import EmailAddress
		user = User.objects.create_user(
			username="existing@example.com",
			email="existing@example.com",
			password="MyPassword123!",
		)
		request = self.factory.get("/")
		social_account = SocialAccount(provider="google", uid="google-uid-12345")
		social_account.extra_data = {"email": "existing@example.com", "name": "Existing User"}
		social_login = SocialLogin(account=social_account)
		social_login.user = User()

		self.adapter.pre_social_login(request, social_login)

		# After pre_social_login, the sociallogin.user should point to
		# the existing user (is_existing == True because user has a pk).
		self.assertTrue(social_login.is_existing)
		self.assertEqual(social_login.user.pk, user.pk)
		# _did_authenticate_by_email should be set for allauth AUTO_CONNECT.
		self.assertEqual(social_login._did_authenticate_by_email, "existing@example.com")
		# Password must NOT be wiped.
		user.refresh_from_db()
		self.assertTrue(user.has_usable_password())
		self.assertTrue(user.check_password("MyPassword123!"))
		# A verified EmailAddress must exist.
		self.assertTrue(EmailAddress.objects.filter(user=user, email="existing@example.com", verified=True).exists())

	def test_new_user_gets_populated_with_google_email_and_username(self):
		from allauth.socialaccount.models import SocialAccount, SocialLogin
		request = self.factory.get("/")
		social_account = SocialAccount(provider="google", uid="google-uid-67890")
		social_login = SocialLogin(account=social_account)
		social_login.user = User()

		user = self.adapter.populate_user(
			request,
			social_login,
			{"email": "newuser@example.com", "first_name": "New", "last_name": "User"},
		)
		self.assertEqual(user.email, "newuser@example.com")
		self.assertEqual(user.username, "newuser@example.com")
		self.assertEqual(user.first_name, "New")
		self.assertEqual(user.last_name, "User")

