import json
from urllib.error import HTTPError
from unittest.mock import Mock, patch

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from .email_backends import BrevoEmailBackend, BrevoEmailBackendError


@override_settings(
    BREVO_API_KEY="test-api-key",
    DEFAULT_FROM_EMAIL="EchoMoments <no-reply@example.test>",
)
class BrevoEmailBackendTests(SimpleTestCase):
    @patch("accounts.email_backends.urlopen")
    def test_sends_password_reset_message_via_https_api(self, urlopen_mock):
        urlopen_mock.return_value.__enter__.return_value.status = 201
        message = EmailMultiAlternatives(
            subject="Reset your password",
            body="Use this one-time link to reset your password.",
            from_email=None,
            to=["Guest <guest@example.test>"],
        )
        message.attach_alternative("<p>Reset your password</p>", "text/html")

        self.assertEqual(BrevoEmailBackend().send_messages([message]), 1)

        request = urlopen_mock.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(payload["sender"], {"name": "EchoMoments", "email": "no-reply@example.test"})
        self.assertEqual(payload["to"], [{"name": "Guest", "email": "guest@example.test"}])
        self.assertEqual(payload["textContent"], "Use this one-time link to reset your password.")
        self.assertEqual(payload["htmlContent"], "<p>Reset your password</p>")
        headers = {name.lower(): value for name, value in request.header_items()}
        self.assertEqual(headers["api-key"], "test-api-key")
        self.assertEqual(urlopen_mock.call_args.kwargs["timeout"], 15)

    @patch("accounts.email_backends.urlopen")
    def test_api_rejection_does_not_leak_api_response(self, urlopen_mock):
        urlopen_mock.side_effect = HTTPError(
            "https://api.brevo.com/v3/smtp/email", 401, "Unauthorized", {}, None
        )
        message = EmailMultiAlternatives(
            subject="Reset", body="Secret reset URL", from_email=None, to=["guest@example.test"]
        )

        with self.assertRaises(BrevoEmailBackendError) as error:
            BrevoEmailBackend().send_messages([message])

        self.assertIn("401", str(error.exception))
        self.assertNotIn("Secret reset URL", str(error.exception))
        self.assertNotIn("test-api-key", str(error.exception))

    @override_settings(BREVO_API_KEY="")
    def test_missing_api_key_fails_loudly(self):
        with self.assertRaises(ImproperlyConfigured):
            BrevoEmailBackend().send_messages([
                EmailMultiAlternatives("Reset", "Body", None, ["guest@example.test"])
            ])

    def test_empty_message_list_does_not_call_api(self):
        self.assertEqual(BrevoEmailBackend().send_messages([]), 0)

