from django.apps import apps
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from events.models import Event, Photo, EventMember
from accounts.models import Activity


@receiver(post_save, sender=Event, dispatch_uid="events.log_created")
def log_event_created(sender, instance, created, **kwargs):
    if created:
        Activity.objects.get_or_create(
            user=instance.created_by, event=instance, title="Created Event",
            description=f"You created the event '{instance.event_name}'",
        )


@receiver(post_save, sender=Photo, dispatch_uid="events.log_photo_uploaded")
def log_photo_uploaded(sender, instance, created, **kwargs):
    if created and instance.uploaded_by_id:
        Activity.objects.create(
            user=instance.uploaded_by, event=instance.event, title="Uploaded Photo",
            description=f"A photo was uploaded to {instance.event.event_name}",
        )


@receiver(post_save, sender=EventMember, dispatch_uid="events.log_member_joined")
def log_member_joined(sender, instance, created, **kwargs):
    if created and instance.role != "host":
        Activity.objects.create(
            user=instance.user, event=instance.event, title="Joined Event",
            description=f"You joined {instance.event.event_name}",
        )


def _schedule_file_delete(storage, name):
    if name:
        transaction.on_commit(
            lambda storage=storage, name=name: storage.delete(name),
            robust=True,
        )


def _connect_private_file_cleanup(model, field_name):
    field = model._meta.get_field(field_name)

    def remove_replaced_file(sender, instance, **kwargs):
        if not instance.pk:
            return
        old_name = sender._base_manager.filter(pk=instance.pk).values_list(field.attname, flat=True).first()
        new_file = getattr(instance, field_name)
        new_name = new_file.name if new_file else ""
        if old_name and old_name != new_name:
            _schedule_file_delete(field.storage, old_name)

    def remove_deleted_file(sender, instance, **kwargs):
        stored_file = getattr(instance, field_name)
        if stored_file and stored_file.name:
            _schedule_file_delete(field.storage, stored_file.name)

    label = model._meta.label_lower
    pre_save.connect(
        remove_replaced_file,
        sender=model,
        dispatch_uid=f"private_file_replace_cleanup:{label}:{field_name}",
    )
    post_delete.connect(
        remove_deleted_file,
        sender=model,
        dispatch_uid=f"private_file_delete_cleanup:{label}:{field_name}",
    )


for _model_label, _field_name in (
    ("events.Event", "cover_photo"),
    ("events.Photo", "image"),
    ("events.Photo", "analysis_image"),
    ("events.UploadJob", "source_file"),
    ("home.Event", "cover_photo"),
    ("accounts.UserProfile", "profile_pic"),
):
    _connect_private_file_cleanup(apps.get_model(_model_label), _field_name)
