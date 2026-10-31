"""Django email backend for Brevo's HTTPS transactional email API."""

import base64
import json
import logging
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class BrevoEmailBackendError(OSError):
    """Raised when Brevo cannot accept a transactional email."""


class BrevoEmailBackend(BaseEmailBackend):
    """Send Django EmailMessage instances through Brevo over HTTPS."""

    api_url = "https://api.brevo.com/v3/smtp/email"
    timeout = 15

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        api_key = getattr(settings, "BREVO_API_KEY", "")
        if not api_key:
            logger.error(
                "Brevo email backend cannot send email: BREVO_API_KEY is not set in environment variables."
            )
            if self.fail_silently:
                return 0
            raise ImproperlyConfigured("Set BREVO_API_KEY to send email through Brevo.")

        sent = 0
        for message in email_messages:
            if not message.recipients():
                continue
            try:
                self._send(message, api_key)
            except (BrevoEmailBackendError, URLError, TimeoutError) as exc:
                logger.error("Brevo could not accept a transactional email: %s", exc)
                if not self.fail_silently:
                    raise
            else:
                sent += 1
        return sent

    def _send(self, message, api_key):
        from_name, from_email = parseaddr(message.from_email or settings.DEFAULT_FROM_EMAIL)
        if not from_email:
            raise ImproperlyConfigured("DEFAULT_FROM_EMAIL must contain a valid sender email address.")

        if "localhost" in from_email or "@example." in from_email:
            logger.warning(
                "DEFAULT_FROM_EMAIL is currently '%s'. Brevo requires a real, verified sender email "
                "(configured in Brevo -> Senders & IPs -> Senders).",
                from_email,
            )

        payload = {
            "sender": {"name": from_name or "EchoMoments", "email": from_email},
            "subject": message.subject,
        }
        for source, target in ((message.to, "to"), (message.cc, "cc"), (message.bcc, "bcc")):
            if source:
                payload[target] = [self._recipient(address) for address in source]

        text_content = message.body
        html_content = text_content if message.content_subtype == "html" else None
        if message.content_subtype != "html":
            for content, mimetype in getattr(message, "alternatives", ()):
                if mimetype == "text/html":
                    html_content = content
                    break
        if text_content and message.content_subtype != "html":
            payload["textContent"] = text_content
        if html_content:
            payload["htmlContent"] = html_content

        reply_to = getattr(message, "reply_to", ())
        if reply_to:
            reply_name, reply_email = parseaddr(reply_to[0])
            if reply_email:
                payload["replyTo"] = {"email": reply_email}
                if reply_name:
                    payload["replyTo"]["name"] = reply_name

        attachments = self._attachments(message)
        if attachments:
            payload["attachment"] = attachments

        request = Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if not 200 <= response.status < 300:
                    raise BrevoEmailBackendError(f"Brevo returned HTTP {response.status}.")
                response.read()
        except HTTPError as exc:
            try:
                error_body = exc.read().decode("utf-8", "replace")
            except Exception:
                error_body = ""
            logger.error("Brevo API error (HTTP %s): %s", exc.code, error_body)
            raise BrevoEmailBackendError(f"Brevo returned HTTP {exc.code}: {error_body}") from None
        except URLError as exc:
            logger.error("Could not connect to Brevo email API: %s", exc)
            raise BrevoEmailBackendError("Could not connect to Brevo's email API.") from exc

    @staticmethod
    def _recipient(address):
        name, email = parseaddr(address)
        recipient = {"email": email or address}
        if name:
            recipient["name"] = name
        return recipient

    @staticmethod
    def _attachments(message):
        attachments = []
        for attachment in getattr(message, "attachments", ()):
            if isinstance(attachment, tuple):
                filename, content = attachment[:2]
            else:
                filename = attachment.get_filename() or "attachment"
                content = attachment.get_payload(decode=True) or b""
            if isinstance(content, str):
                content = content.encode(message.encoding or settings.DEFAULT_CHARSET)
            attachments.append({
                "name": filename,
                "content": base64.b64encode(content).decode("ascii"),
            })
        return attachments
