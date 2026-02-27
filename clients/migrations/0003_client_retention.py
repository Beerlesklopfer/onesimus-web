from django.db import migrations, models


class Migration(migrations.Migration):
    initial = False

    dependencies = [
        ('clients', '0002_alter_client_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='file_retention_days',
            field=models.IntegerField(default=60, help_text='File retention in days'),
        ),
        migrations.AddField(
            model_name='client',
            name='job_retention_days',
            field=models.IntegerField(default=180, help_text='Job retention in days'),
        ),
    ]
