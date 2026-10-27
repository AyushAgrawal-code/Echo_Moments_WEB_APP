from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0002_migrate_guest_data'),
    ]

    operations = [
        # Remove Photo.guest
        migrations.RemoveField(
            model_name='photo',
            name='guest',
        ),

        # Delete Guest model
        migrations.DeleteModel(
            name='Guest',
        ),
    ]
