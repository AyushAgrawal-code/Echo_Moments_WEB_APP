from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


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
