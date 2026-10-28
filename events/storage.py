from django.conf import settings
from django.core.files.storage import FileSystemStorage


if settings.USE_S3:
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
