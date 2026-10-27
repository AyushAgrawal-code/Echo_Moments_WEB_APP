from django.db.models.signals import post_save
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
