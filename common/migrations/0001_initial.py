from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Setting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(db_index=True, help_text="Unique dot-separated key, e.g. 'director.host'", max_length=120, unique=True)),
                ('value', models.JSONField(default=None, help_text='JSON value (string, number, bool, list, dict, null)', null=True)),
                ('description', models.CharField(blank=True, help_text='Human-readable description for the admin UI', max_length=255)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Application Setting',
                'verbose_name_plural': 'Application Settings',
                'ordering': ['key'],
            },
        ),
        migrations.CreateModel(
            name='UserPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope', models.CharField(db_index=True, help_text="Feature area, e.g. 'jobs.filter' or 'ui'", max_length=100)),
                ('key', models.CharField(help_text='Preference key within the scope', max_length=100)),
                ('value', models.JSONField(default=None, help_text='JSON value', null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='preferences',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'User Preference',
                'verbose_name_plural': 'User Preferences',
                'ordering': ['scope', 'key'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='userpreference',
            unique_together={('user', 'scope', 'key')},
        ),
    ]
