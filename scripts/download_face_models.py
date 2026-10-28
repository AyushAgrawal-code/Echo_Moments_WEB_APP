"""Download pinned OpenCV Zoo models and their licenses for face matching."""

import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models"
RELEASES = {
    "face_detection_yunet_2023mar.onnx": {
        "revision": "f12e12798e8314f7c074a6656816c048dcc95b7a",
        "path": "models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    },
    "face_recognition_sface_2021dec.onnx": {
        "revision": "ba91a3b91d00d76e86540d4013f944bd6b514e39",
        "path": "models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "sha256": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    },
}


def download(url, destination, expected_sha256=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "EchoMoments model setup"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=60) as response:
        fd, temp_name = tempfile.mkstemp(dir=destination.parent, prefix=destination.name + ".")
        try:
            with os.fdopen(fd, "wb") as temp_file:
                while chunk := response.read(1024 * 1024):
                    digest.update(chunk)
                    temp_file.write(chunk)
            if expected_sha256 and digest.hexdigest() != expected_sha256:
                raise ValueError(f"SHA-256 mismatch for {destination.name}")
            os.replace(temp_name, destination)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise


def main():
    for filename, model in RELEASES.items():
        destination = MODEL_DIR / filename
        if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == model["sha256"]:
            print(f"Already present: {filename}")
            continue
        url = (
            "https://github.com/opencv/opencv_zoo/raw/"
            f"{model['revision']}/{model['path']}"
        )
        print(f"Downloading {filename} from pinned OpenCV Zoo revision...")
        download(url, destination, model["sha256"])

    licenses = {
        "yunet-MIT.txt": "f12e12798e8314f7c074a6656816c048dcc95b7a/models/face_detection_yunet/LICENSE",
        "sface-Apache-2.0.txt": "ba91a3b91d00d76e86540d4013f944bd6b514e39/models/face_recognition_sface/LICENSE",
    }
    license_dir = MODEL_DIR / "licenses"
    for filename, revision_path in licenses.items():
        url = "https://raw.githubusercontent.com/opencv/opencv_zoo/" + revision_path
        download(url, license_dir / filename)
    print(f"Face models and license files are ready in {MODEL_DIR}")


if __name__ == "__main__":
    main()
