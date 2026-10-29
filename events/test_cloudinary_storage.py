from unittest.mock import Mock, patch

from django.core.files.base import ContentFile
from django.test import SimpleTestCase

from .storage import CloudinaryPrivateStorage


class CloudinaryPrivateStorageTests(SimpleTestCase):
    def setUp(self):
        self.storage = CloudinaryPrivateStorage("echomoments/photos")
        self.api = Mock()
        self.uploader = Mock()
        self.utils = Mock()
        self.sdk_patch = patch.object(
            CloudinaryPrivateStorage,
            "_sdk",
            return_value=(self.api, self.uploader, self.utils),
        )
        self.sdk_patch.start()
        self.addCleanup(self.sdk_patch.stop)

    def test_uploads_images_as_authenticated_and_keeps_a_relative_storage_name(self):
        self.uploader.upload.return_value = {
            "public_id": "echomoments/photos/event_photos/holiday",
            "format": "jpg",
        }

        stored_name = self.storage._save("event_photos/holiday.jpg", ContentFile(b"image-bytes"))

        self.assertEqual(stored_name, "event_photos/holiday.jpg")
        self.uploader.upload.assert_called_once()
        args, kwargs = self.uploader.upload.call_args
        self.assertEqual(args[0].read(), b"image-bytes")
        self.assertEqual(kwargs["public_id"], "echomoments/photos/event_photos/holiday")
        self.assertEqual(kwargs["resource_type"], "image")
        self.assertEqual(kwargs["type"], "authenticated")
        self.assertFalse(kwargs["overwrite"])

    def test_open_uses_a_short_lived_signed_private_url(self):
        self.utils.private_download_url.return_value = "https://secure.example.test/image"
        response = Mock()
        response.read.return_value = b"private-image"
        urlopen_mock = patch("events.storage.urlopen")
        mocked_urlopen = urlopen_mock.start()
        mocked_urlopen.return_value.__enter__.return_value = response
        self.addCleanup(urlopen_mock.stop)

        with self.storage._open("event_photos/holiday.jpg") as image:
            self.assertEqual(image.read(), b"private-image")

        self.utils.private_download_url.assert_called_once()
        self.assertEqual(self.utils.private_download_url.call_args.args[:2], (
            "echomoments/photos/event_photos/holiday", "jpg"
        ))
        self.assertEqual(self.utils.private_download_url.call_args.kwargs["type"], "authenticated")
        self.assertEqual(mocked_urlopen.call_args.args[0], "https://secure.example.test/image")

    def test_delete_targets_authenticated_image_only(self):
        self.storage.delete("event_photos/holiday.jpg")

        self.uploader.destroy.assert_called_once_with(
            "echomoments/photos/event_photos/holiday",
            resource_type="image",
            type="authenticated",
            invalidate=True,
        )

    def test_exists_returns_false_for_cloudinary_not_found(self):
        error = OSError("not found")
        error.http_status = 404
        self.api.resource.side_effect = error

        self.assertFalse(self.storage.exists("event_photos/missing.png"))

    def test_exists_propagates_authentication_and_network_errors(self):
        self.api.resource.side_effect = OSError("service unavailable")

        with self.assertRaisesRegex(OSError, "service unavailable"):
            self.storage.exists("event_photos/photo.jpg")

