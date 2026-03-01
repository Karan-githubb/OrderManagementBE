# Draft order: per-user instead of per-pharmacy

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def clear_drafts(apps, schema_editor):
    DraftOrder = apps.get_model('drafts', 'DraftOrder')
    DraftOrder.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('drafts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='draftorder',
            name='user',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='draft_order', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(clear_drafts, migrations.RunPython.noop),
        migrations.RemoveField(model_name='draftorder', name='pharmacy'),
        migrations.AlterField(
            model_name='draftorder',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='draft_order', to=settings.AUTH_USER_MODEL),
        ),
    ]
