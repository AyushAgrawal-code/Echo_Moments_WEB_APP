import uuid

from django.db import migrations, models


def populate_invite_tokens(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    for event in Event.objects.filter(invite_token__isnull=True).iterator():
        event.invite_token = uuid.uuid4()
        event.save(update_fields=["invite_token"])


class Migration(migrations.Migration):
    dependencies = [("events", "0014_photo_face_embedding_model_version_and_more")]

    operations = [
        migrations.AddField(
            model_name="event",
            name="invite_token",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(populate_invite_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="event",
            name="invite_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
