"""Common models: global settings and per-user preferences."""
from django.conf import settings
from django.db import models


class Setting(models.Model):
    """
    Global application settings (admin-managed).

    Stores typed configuration values that apply to the whole application:
    director host/port, default page sizes, feature flags, etc.
    Values are stored as JSON so any type is supported.

    Usage:
        Setting.get('director_host', default='localhost')
        Setting.set('director_host', '10.0.0.1', description='Bareos Director hostname')
    """
    key         = models.CharField(max_length=120, unique=True, db_index=True,
                                   help_text="Unique dot-separated key, e.g. 'director.host'")
    value       = models.JSONField(default=None, null=True,
                                   help_text="JSON value (string, number, bool, list, dict, null)")
    description = models.CharField(max_length=255, blank=True,
                                   help_text="Human-readable description for the admin UI")
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']
        verbose_name = 'Application Setting'
        verbose_name_plural = 'Application Settings'

    def __str__(self):
        return f'{self.key} = {self.value!r}'

    @classmethod
    def get(cls, key, default=None):
        """Return the value for *key*, or *default* if not found."""
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value, description=''):
        """Create or update the setting for *key*. Returns the instance."""
        obj, _ = cls.objects.update_or_create(
            key=key,
            defaults={'value': value, 'description': description},
        )
        return obj

    @classmethod
    def get_all(cls):
        """Return all settings as a plain dict {key: value}."""
        return {s.key: s.value for s in cls.objects.all()}


class UserPreference(models.Model):
    """
    Per-user UI preferences and state (auto-saved by the frontend).

    Scoped key-value store so each feature area can manage its own state
    without key collisions:

        scope='jobs.filter'  key='status_open'  value=True
        scope='jobs.filter'  key='per_page'      value=50
        scope='ui'           key='filter_panel'  value='open'

    Python usage:
        UserPreference.get(user, 'jobs.filter', 'per_page', default=25)
        UserPreference.set(user, 'jobs.filter', 'per_page', 50)

    JS usage (via /common/preferences/ API + settings.js):
        await OnesimSettings.get('jobs.filter', 'per_page', 25)
        await OnesimSettings.set('jobs.filter', 'per_page', 50)
    """
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preferences',
    )
    scope      = models.CharField(max_length=100, db_index=True,
                                  help_text="Feature area, e.g. 'jobs.filter' or 'ui'")
    key        = models.CharField(max_length=100,
                                  help_text="Preference key within the scope")
    value      = models.JSONField(default=None, null=True,
                                  help_text="JSON value")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('user', 'scope', 'key')]
        ordering = ['scope', 'key']
        verbose_name = 'User Preference'
        verbose_name_plural = 'User Preferences'

    def __str__(self):
        return f'{self.user} / {self.scope}.{self.key} = {self.value!r}'

    @classmethod
    def get(cls, user, scope, key, default=None):
        """Return the value for user/scope/key, or *default* if not found."""
        try:
            return cls.objects.get(user=user, scope=scope, key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, user, scope, key, value):
        """Create or update a preference. Returns the instance."""
        obj, _ = cls.objects.update_or_create(
            user=user, scope=scope, key=key,
            defaults={'value': value},
        )
        return obj

    @classmethod
    def get_scope(cls, user, scope):
        """Return all preferences for user in scope as {key: value}."""
        return {p.key: p.value for p in cls.objects.filter(user=user, scope=scope)}

    @classmethod
    def set_many(cls, user, scope, data: dict):
        """Bulk-upsert multiple keys in one scope."""
        for key, value in data.items():
            cls.set(user, scope, key, value)
