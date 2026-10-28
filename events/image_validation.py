"""Shared validation for images uploaded as photos, covers, selfies, or avatars."""

import os
import re

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


MAX_UPLOAD_SIZE = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 30_000_000
MAX_IMAGE_FRAMES = 100
SUPPORTED_IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "GIF": ("image/gif", "gif"),
    "WEBP": ("image/webp", "webp"),
}


def safe_image_filename(original_name, extension):
    """Keep a harmless display name while deriving the suffix from image bytes."""
    basename = os.path.basename(str(original_name).replace("\\", "/"))
    stem = os.path.splitext(basename)[0]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-_")[:80]
    return f"{stem or 'photo'}.{extension}"


def _has_clean_image_end(uploaded_file, image_format):
    """Reject truncated images and payloads appended after the image container."""
    original_position = uploaded_file.tell()
    try:
        uploaded_file.seek(0, os.SEEK_END)
        size = uploaded_file.tell()
        if image_format == "JPEG" and size >= 2:
            uploaded_file.seek(-2, os.SEEK_END)
            return uploaded_file.read(2) == b"\xff\xd9"
        if image_format == "PNG" and size >= 12:
            uploaded_file.seek(-12, os.SEEK_END)
            return uploaded_file.read(12) == b"\x00\x00\x00\x00IEND\xaeB`\x82"
        if image_format == "GIF" and size >= 1:
            uploaded_file.seek(-1, os.SEEK_END)
            return uploaded_file.read(1) == b";"
        if image_format == "WEBP" and size >= 12:
            uploaded_file.seek(0)
            header = uploaded_file.read(12)
            return (
                header[:4] == b"RIFF"
                and header[8:12] == b"WEBP"
                and int.from_bytes(header[4:8], "little") + 8 == size
            )
        return False
    finally:
        uploaded_file.seek(original_position)


def validate_image_upload(uploaded_file):
    """Validate bytes, format, size and decoded frames; rewind and return MIME/extension."""
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        raise ValidationError("Images must be 10 MB or smaller.")

    try:
        with Image.open(uploaded_file) as image:
            image_format = image.format
            image_info = SUPPORTED_IMAGE_FORMATS.get(image_format)
            if not image_info:
                raise ValidationError("Choose a JPEG, PNG, GIF, or WebP image.")
            try:
                frame_count = int(getattr(image, "n_frames", 1))
            except (TypeError, ValueError):
                frame_count = 1
            if frame_count > MAX_IMAGE_FRAMES:
                raise ValidationError("Images with more than 100 frames are not supported.")
            total_pixels = 0
            for frame_number in range(frame_count):
                image.seek(frame_number)
                total_pixels += image.width * image.height
                if total_pixels > MAX_IMAGE_PIXELS:
                    raise ValidationError("Images must be 30 megapixels or smaller.", code="image_too_many_pixels")
                image.load()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, EOFError, ValueError, Image.DecompressionBombError) as exc:
        raise ValidationError("The uploaded file is not a valid image.") from exc

    if not _has_clean_image_end(uploaded_file, image_format):
        raise ValidationError("The image is truncated or contains trailing data.")
    uploaded_file.seek(0)
    return image_info
