import logging
import os
import threading
import time

from django.core.management import BaseCommand, call_command
from django.db import close_old_connections


logger = logging.getLogger(__name__)


def _run_queue_forever(command_name):
    while True:
        try:
            close_old_connections()
            call_command(command_name)
        except Exception:
            logger.exception("Background queue %s stopped unexpectedly; restarting.", command_name)
            time.sleep(2)
        finally:
            close_old_connections()


class Command(BaseCommand):
    help = "Run the small free-demo web server with its database-backed queue workers."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
        parser.add_argument("--threads", type=int, default=4)

    def handle(self, *args, **options):
        try:
            from waitress import serve
        except ImportError as exc:
            raise RuntimeError("Install waitress to run the single-instance demo deployment.") from exc

        for command_name in ("process_upload_queue", "process_face_index_queue"):
            thread = threading.Thread(
                target=_run_queue_forever,
                args=(command_name,),
                name=command_name,
                daemon=True,
            )
            thread.start()

        self.stdout.write(f"Serving EchoMoments on {options['host']}:{options['port']} with queue workers.")
        from echoMoments.wsgi import application
        serve(
            application,
            host=options["host"],
            port=options["port"],
            threads=max(2, options["threads"]),
            connection_limit=100,
            channel_timeout=30,
        )
