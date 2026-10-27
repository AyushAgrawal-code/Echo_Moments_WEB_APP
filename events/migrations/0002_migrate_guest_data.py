from django.db import migrations
from django.conf import settings
import random
import string


def generate_username():
    return "guest_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


def forwards(apps, schema_editor):
    Guest = apps.get_model('events', 'Guest')
    EventMember = apps.get_model('events', 'EventMember')
    Photo = apps.get_model('events', 'Photo')

    UserModel = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0], settings.AUTH_USER_MODEL.split('.')[1])

    # --------- MIGRATE GUEST → EVENTMEMBER -----------
    for guest in Guest.objects.all():
        email = (guest.email or "").strip().lower()

        # Try to match real user by email
        user = None
        if email:
            user = UserModel.objects.filter(email__iexact=email).first()

        # No matching user → create placeholder account
        if not user:
            username = generate_username()
            while UserModel.objects.filter(username=username).exists():
                username = generate_username()

            user = UserModel.objects.create(
                username=username,
                email=email,
                is_active=False
            )
            user.set_unusable_password()
            user.save()

        # Create EventMember entry
        EventMember.objects.get_or_create(
            user=user,
            event=guest.event,
            defaults={
                "role": "guest",
                "join_method": "invite",
                "joined_at": guest.joined_at,
                "is_active": guest.is_active,
            }
        )

    # ---------- MIGRATE PHOTO.guest → uploaded_by ----------
    for photo in Photo.objects.all():
        guest = photo.guest
        if guest and guest.email:
            user = UserModel.objects.filter(email__iexact=guest.email).first()
            if user:
                photo.uploaded_by = user
                photo.save()


def backwards(apps, schema_editor):
    pass  # no reverse operation


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
