"""On-device OpenCV YuNet/SFace face extraction and private vector encryption."""

import base64
import hashlib
import json
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from django.conf import settings
from PIL import Image, UnidentifiedImageError
from PIL import ImageOps


MAX_IMAGE_PIXELS = 30_000_000
MIN_FACE_IMAGE_SIDE = 80
MAX_FACE_SCAN_EDGE = 1920


class FaceMatchingUnavailable(RuntimeError):
    pass


class FaceEnrollmentError(ValueError):
    pass


def model_version():
    return getattr(settings, "FACE_MODEL_VERSION", "opencv-sface-2021dec-v1")


def _model_paths():
    detector = Path(getattr(settings, "FACE_DETECTOR_MODEL", settings.BASE_DIR / "models" / "face_detection_yunet_2023mar.onnx"))
    recognizer = Path(getattr(settings, "FACE_RECOGNIZER_MODEL", settings.BASE_DIR / "models" / "face_recognition_sface_2021dec.onnx"))
    if not detector.is_file() or not recognizer.is_file():
        raise FaceMatchingUnavailable(
            "Face matching models are not installed. Configure FACE_DETECTOR_MODEL and FACE_RECOGNIZER_MODEL."
        )
    return detector, recognizer


@lru_cache(maxsize=1)
def _models():
    detector_path, recognizer_path = _model_paths()
    try:
        import cv2
    except ImportError as exc:
        raise FaceMatchingUnavailable("Install opencv-contrib-python-headless to enable face matching.") from exc

    if not hasattr(cv2, "FaceDetectorYN") or not hasattr(cv2, "FaceRecognizerSF"):
        raise FaceMatchingUnavailable("The installed OpenCV build does not include YuNet/SFace support.")
    try:
        detector = cv2.FaceDetectorYN.create(str(detector_path), "", (320, 320), 0.85, 0.3, 5000)
        recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), "")
    except cv2.error as exc:
        raise FaceMatchingUnavailable("OpenCV could not load the configured YuNet/SFace models.") from exc
    return cv2, detector, recognizer


def _validate_face_image_dimensions(image_bytes):
    try:
        with Image.open(BytesIO(image_bytes)) as source_image:
            width, height = source_image.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise FaceEnrollmentError("The image could not be read.") from exc
    if width < MIN_FACE_IMAGE_SIDE or height < MIN_FACE_IMAGE_SIDE:
        raise FaceEnrollmentError("Use a larger, clearer photo for face matching.")
    if width * height > MAX_IMAGE_PIXELS:
        raise FaceEnrollmentError("Images larger than 30 megapixels aren't supported for face matching.")
    return width, height


def extract_face_embeddings(image_bytes):
    """Detect and align faces on a bounded analysis image to limit peak RAM."""
    _validate_face_image_dimensions(image_bytes)
    try:
        import numpy as np
    except ImportError as exc:
        raise FaceMatchingUnavailable("Install numpy to enable face matching.") from exc

    cv2, detector, recognizer = _models()
    encoded = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    del encoded
    if image is None:
        raise FaceEnrollmentError("The image could not be decoded.")

    decoded_height, decoded_width = image.shape[:2]
    if decoded_width * decoded_height > MAX_IMAGE_PIXELS:
        raise FaceEnrollmentError("Images larger than 30 megapixels aren't supported for face matching.")
    if decoded_width < MIN_FACE_IMAGE_SIDE or decoded_height < MIN_FACE_IMAGE_SIDE:
        raise FaceEnrollmentError("Use a larger, clearer photo for face matching.")

    detector.setInputSize((decoded_width, decoded_height))
    _, detections = detector.detect(image)
    if detections is None or len(detections) == 0:
        return []

    vectors = []
    for detection in detections:
        aligned = recognizer.alignCrop(image, detection)
        feature = np.asarray(recognizer.feature(aligned), dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(feature))
        if norm:
            vectors.append((feature / norm).tolist())
    return vectors


def create_analysis_image(image_bytes):
    """Make a private, orientation-corrected JPEG copy for face scanning."""
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail((MAX_FACE_SCAN_EDGE, MAX_FACE_SCAN_EDGE), Image.Resampling.LANCZOS)
            if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            output = BytesIO()
            image.save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise FaceEnrollmentError("The event photo could not be prepared for face matching.") from exc


def extract_enrollment_embedding(image_bytes):
    # Enrollment uses the same bounded analysis size as event-photo indexing
    # so a large phone selfie cannot trigger a full-resolution OpenCV decode.
    analysis_bytes = create_analysis_image(image_bytes)
    embeddings = extract_face_embeddings(analysis_bytes)
    del analysis_bytes
    if len(embeddings) != 1:
        if not embeddings:
            raise FaceEnrollmentError("We couldn't detect a face in that selfie. Try a clear, front-facing photo with good lighting.")
        raise FaceEnrollmentError(
            "We detected more than one face. Choose a selfie with only you in the frame."
        )
    return embeddings[0]


def encrypt_embedding(embedding):
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise FaceMatchingUnavailable("Install cryptography to enable encrypted face templates.") from exc

    configured_key = getattr(settings, "FACE_ENCRYPTION_KEY", "")
    if configured_key:
        key = configured_key.encode("ascii")
    else:
        # Domain-separated key derived from SECRET_KEY for local use. Deployments
        # should set FACE_ENCRYPTION_KEY separately and keep it stable.
        digest = hashlib.sha256((settings.SECRET_KEY + ":echomoments-face-v1").encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
    try:
        return Fernet(key).encrypt(json.dumps(embedding, separators=(",", ":")).encode("utf-8")).decode("ascii")
    except (ValueError, TypeError) as exc:
        raise FaceMatchingUnavailable("FACE_ENCRYPTION_KEY must be a valid Fernet key.") from exc


def encrypt_face_embeddings(embeddings):
    """Encrypt face vectors cached for one private event photo."""
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise FaceMatchingUnavailable("Install cryptography to enable encrypted face templates.") from exc

    configured_key = getattr(settings, "FACE_ENCRYPTION_KEY", "")
    if configured_key:
        key = configured_key.encode("ascii")
    else:
        digest = hashlib.sha256((settings.SECRET_KEY + ":echomoments-face-v1").encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
    try:
        payload = json.dumps(embeddings, separators=(",", ":")).encode("utf-8")
        return Fernet(key).encrypt(payload).decode("ascii")
    except (ValueError, TypeError) as exc:
        raise FaceMatchingUnavailable("FACE_ENCRYPTION_KEY must be a valid Fernet key.") from exc


def decrypt_face_embeddings(ciphertext):
    """Decrypt a photo's cached face vectors inside the server process only."""
    from cryptography.fernet import Fernet, InvalidToken

    configured_key = getattr(settings, "FACE_ENCRYPTION_KEY", "")
    if configured_key:
        key = configured_key.encode("ascii")
    else:
        digest = hashlib.sha256((settings.SECRET_KEY + ":echomoments-face-v1").encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
    try:
        vectors = json.loads(Fernet(key).decrypt(ciphertext.encode("ascii")))
        if not isinstance(vectors, list) or any(not isinstance(vector, list) for vector in vectors):
            raise ValueError("Invalid cached face vectors")
        return vectors
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise FaceMatchingUnavailable("The cached event photo features could not be decrypted.") from exc


def decrypt_embedding(ciphertext):
    from cryptography.fernet import Fernet, InvalidToken

    configured_key = getattr(settings, "FACE_ENCRYPTION_KEY", "")
    if configured_key:
        key = configured_key.encode("ascii")
    else:
        digest = hashlib.sha256((settings.SECRET_KEY + ":echomoments-face-v1").encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
    try:
        return json.loads(Fernet(key).decrypt(ciphertext.encode("ascii")))
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise FaceMatchingUnavailable("The stored face template could not be decrypted.") from exc


def similarity(left, right):
    """Cosine similarity for the normalized SFace feature vectors."""
    if len(left) != len(right) or not left:
        return 0.0
    return sum(float(a) * float(b) for a, b in zip(left, right))
