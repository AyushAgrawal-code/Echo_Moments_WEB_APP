import io
import os
import time
from pathlib import PurePosixPath
from urllib.request import urlopen

from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible

from cloudinary.exceptions import NotFound


@deconstructible
class CloudinaryPrivateStorage(Storage):
    """Store images as authenticated Cloudinary assets and sign every read."""

    delivery_type = "authenticated"
    resource_type = "image"

    def __init__(self, prefix):
        self.prefix = prefix.strip("/")

    @staticmethod
    def _sdk():
        import cloudinary
        import cloudinary.api
        import cloudinary.uploader
        import cloudinary.utils

        cloudinary.config(secure=True)
        return cloudinary.api, cloudinary.uploader, cloudinary.utils

    def _public_id(self, name):
        path = PurePosixPath(str(name).replace("\\", "/").lstrip("/"))
        if not path.parts or any(part in ("", ".", "..") for part in path.parts):
            raise ValueError("Invalid Cloudinary storage name.")
        stem = path.with_suffix("").as_posix() if path.suffix else path.as_posix()
        return f"{self.prefix}/{stem}"

    def _format(self, name):
        return PurePosixPath(str(name)).suffix.lstrip(".").lower()

    def _signed_url(self, name, expires_in=300):
        api, uploader, utils = self._sdk()
        image_format = self._format(name)
        if not image_format:
            raise ValueError("Cloudinary image names must include their file extension.")
        return utils.private_download_url(
            self._public_id(name),
            image_format,
            resource_type=self.resource_type,
            type=self.delivery_type,
            expires_at=int(time.time()) + expires_in,
        )

    def _open(self, name, mode="rb"):
        if mode not in ("rb", "r"):
            raise ValueError("Cloudinary storage supports read-only access.")
        with urlopen(self._signed_url(name, expires_in=60), timeout=30) as response:
            return io.BytesIO(response.read())

    def _save(self, name, content):
        _, uploader, _ = self._sdk()
        content.seek(0)
        payload = content.read()
        if not payload:
            raise ValueError("Cannot store an empty image.")
        image_format = self._format(name)
        result = uploader.upload(
            io.BytesIO(payload),
            public_id=self._public_id(name),
            resource_type=self.resource_type,
            type=self.delivery_type,
            overwrite=False,
            use_filename=False,
            unique_filename=False,
        )
        public_id = result.get("public_id")
        stored_format = result.get("format") or image_format
        if not public_id or not stored_format:
            raise OSError("Cloudinary did not return a stored image identifier.")
        relative_name = PurePosixPath(str(name).replace("\\", "/")).with_suffix("").as_posix()
        return f"{relative_name}.{stored_format.lower()}"

    def delete(self, name):
        if not name:
            return
        _, uploader, _ = self._sdk()
        uploader.destroy(
            self._public_id(name),
            resource_type=self.resource_type,
            type=self.delivery_type,
            invalidate=True,
        )

    def exists(self, name):
        if not name:
            return False
        api, _, _ = self._sdk()
        try:
            api.resource(
                self._public_id(name),
                resource_type=self.resource_type,
                type=self.delivery_type,
            )
            return True
        except NotFound:
            return False

    def size(self, name):
        api, _, _ = self._sdk()
        result = api.resource(
            self._public_id(name),
            resource_type=self.resource_type,
            type=self.delivery_type,
        )
        return int(result["bytes"])

    def url(self, name):
        return self._signed_url(name)


if settings.USE_CLOUDINARY:
    class PrivateUploadStorage(CloudinaryPrivateStorage):
        """Store pending uploads privately in a separate Cloudinary prefix."""

        def __init__(self):
            super().__init__("echomoments/uploads")


    class PrivatePhotoStorage(CloudinaryPrivateStorage):
        """Store event images privately in a separate Cloudinary prefix."""

        def __init__(self):
            super().__init__("echomoments/photos")

elif settings.USE_S3:
    from botocore.config import Config
    from storages.backends.s3 import S3Storage

    _s3_client_config = Config(s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE})

    class PrivateUploadStorage(S3Storage):
        """Stage upload jobs in a private object-store prefix."""

        def __init__(self, *args, **kwargs):
            kwargs.setdefault("location", "private-upload-queue")
            kwargs.setdefault("bucket_name", settings.AWS_STORAGE_BUCKET_NAME)
            kwargs.setdefault("querystring_auth", True)
            kwargs.setdefault("default_acl", None)
            kwargs.setdefault("file_overwrite", False)
            kwargs.setdefault("custom_domain", False)
            kwargs.setdefault("client_config", _s3_client_config)
            super().__init__(*args, **kwargs)

    class PrivatePhotoStorage(S3Storage):
        """Store event assets privately; application views authorize each read."""

        def __init__(self, *args, **kwargs):
            kwargs.setdefault("location", "private-event-photos")
            kwargs.setdefault("bucket_name", settings.AWS_STORAGE_BUCKET_NAME)
            kwargs.setdefault("querystring_auth", True)
            kwargs.setdefault("default_acl", None)
            kwargs.setdefault("file_overwrite", False)
            kwargs.setdefault("custom_domain", False)
            kwargs.setdefault("client_config", _s3_client_config)
            super().__init__(*args, **kwargs)
else:
    class PrivateUploadStorage(FileSystemStorage):
        """Stage queued uploads outside MEDIA_ROOT so pending files are not public."""

        def __init__(self, *args, **kwargs):
            kwargs.setdefault("location", settings.BASE_DIR / "private_uploads")
            kwargs.setdefault("base_url", None)
            super().__init__(*args, **kwargs)


    class PrivatePhotoStorage(FileSystemStorage):
        """Keep event photos outside MEDIA_ROOT; views gate reads by membership."""

        def __init__(self, *args, **kwargs):
            kwargs.setdefault("location", settings.BASE_DIR / "private_media")
            kwargs.setdefault("base_url", None)
            super().__init__(*args, **kwargs)
