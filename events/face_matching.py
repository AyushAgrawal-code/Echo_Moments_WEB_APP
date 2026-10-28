"""On-device OpenCV YuNet/SFace face extraction and private vector encryption."""

import base64
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings


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


def extract_face_embeddings(image_bytes):
    """Return normalized embeddings for every detected face in an image."""
    try:
        import numpy as np
    except ImportError as exc:
        raise FaceMatchingUnavailable("Install numpy to enable face matching.") from exc
    cv2, detector, recognizer = _models()
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise FaceEnrollmentError("The image could not be decoded.")
    height, width = image.shape[:2]
    if width < 80 or height < 80:
        raise FaceEnrollmentError("Use a larger, clearer photo for face matching.")
    detector.setInputSize((width, height))
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


def extract_enrollment_embedding(image_bytes):
    embeddings = extract_face_embeddings(image_bytes)
    if len(embeddings) != 1:
        raise FaceEnrollmentError(
            "Upload a clear photo with exactly one visible face. We do not keep the selfie."
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
