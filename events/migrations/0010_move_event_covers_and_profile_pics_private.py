from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import migrations

from events.storage import PrivatePhotoStorage


def move_into_private(apps, schema_editor):
    private_storage = PrivatePhotoStorage()
    for app_label, model_name, field_name in (
        ("events", "Event", "cover_photo"),
        ("home", "Event", "cover_photo"),
        ("accounts", "UserProfile", "profile_pic"),
    ):
        model = apps.get_model(app_label, model_name)
        for row in model.objects.exclude(**{field_name: ""}).iterator():
            old_name = getattr(row, field_name).name
            if not old_name or not default_storage.exists(old_name):
                continue
            with default_storage.open(old_name, "rb") as source:
                new_name = private_storage.save(old_name, ContentFile(source.read()))
            setattr(row, field_name, new_name)
            row.save(update_fields=[field_name])
            default_storage.delete(old_name)


def restore_to_public_media(apps, schema_editor):
    private_storage = PrivatePhotoStorage()
    for app_label, model_name, field_name in (
        ("events", "Event", "cover_photo"),
        ("home", "Event", "cover_photo"),
        ("accounts", "UserProfile", "profile_pic"),
    ):
        model = apps.get_model(app_label, model_name)
        for row in model.objects.exclude(**{field_name: ""}).iterator():
            old_name = getattr(row, field_name).name
            if not old_name or not private_storage.exists(old_name):
                continue
            with private_storage.open(old_name, "rb") as source:
                new_name = default_storage.save(old_name, ContentFile(source.read()))
            setattr(row, field_name, new_name)
            row.save(update_fields=[field_name])
            private_storage.delete(old_name)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_alter_userprofile_profile_pic"),
        ("home", "0002_alter_event_cover_photo"),
        ("events", "0009_eventmember_face_consent_at_and_more"),
    ]

    operations = [
        migrations.RunPython(move_into_private, restore_to_public_media),
    ]
