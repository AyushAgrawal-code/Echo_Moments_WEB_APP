from django.core.management.base import BaseCommand, CommandError

from events.face_matching import _models


class Command(BaseCommand):
    help = "Verify OpenCV YuNet/SFace dependencies and configured model files."

    def handle(self, *args, **options):
        try:
            import numpy

            cv2, _, _ = _models()
        except Exception as exc:
            raise CommandError(f"Face matching is not ready: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Face matching is ready (OpenCV {cv2.__version__}, NumPy {numpy.__version__}; YuNet/SFace loaded)."
            )
        )
