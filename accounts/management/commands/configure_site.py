import os

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Set the Sites framework domain used for absolute links in email."

    def handle(self, *args, **options):
        domain = os.environ.get("SITE_DOMAIN") or os.environ.get("RENDER_EXTERNAL_HOSTNAME")
        if not domain:
            if not settings.DEBUG:
                raise CommandError("Set SITE_DOMAIN or RENDER_EXTERNAL_HOSTNAME before configuring the site.")
            domain = "127.0.0.1:8000"

        domain = domain.removeprefix("https://").removeprefix("http://").strip("/")
        if not domain or "/" in domain:
            raise CommandError("SITE_DOMAIN must be a hostname, optionally with a port.")

        Site.objects.update_or_create(
            id=settings.SITE_ID,
            defaults={"domain": domain, "name": "EchoMoments"},
        )
        self.stdout.write(self.style.SUCCESS(f"Django Site domain configured for {domain}."))
