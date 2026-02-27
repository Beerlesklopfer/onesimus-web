"""Storage models for pool and volume management."""
from django.db import models


class Storage(models.Model):
    """Storage daemon (File-SD, Tape-SD …)."""

    TYPE_CHOICES = [
        ('File', 'File'),
        ('Tape', 'Tape'),
        ('Cloud', 'Cloud'),
    ]
    STATUS_CHOICES = [
        ('online',  'Online'),
        ('offline', 'Offline'),
        ('unknown', 'Unknown'),
    ]

    bareos_id    = models.IntegerField(unique=True, db_index=True)
    name         = models.CharField(max_length=120, unique=True, db_index=True)
    address      = models.CharField(max_length=200, blank=True)
    port         = models.IntegerField(default=9103)
    storage_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='File')
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown',
                                    db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Pool(models.Model):
    """Storage pool (logical grouping of volumes)."""

    bareos_id = models.IntegerField(unique=True, db_index=True)
    name      = models.CharField(max_length=120, unique=True, db_index=True)
    storage   = models.ForeignKey(Storage, on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name='pools')

    pool_type              = models.CharField(max_length=50, default='Backup')
    max_volumes            = models.IntegerField(default=0, help_text='0 = unlimited')
    use_catalog            = models.BooleanField(default=True)
    recycle_oldest_volume  = models.BooleanField(default=False)
    recycle_current_volume = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Volume(models.Model):
    """Individual tape or disk volume."""

    STATUS_CHOICES = [
        ('Append',   'Append'),
        ('Archive',  'Archive'),
        ('Cleaning', 'Cleaning'),
        ('Disabled', 'Disabled'),
        ('Error',    'Error'),
        ('Full',     'Full'),
        ('Recycle',  'Recycle'),
        ('Purged',   'Purged'),
    ]

    bareos_id = models.IntegerField(unique=True, db_index=True)
    name      = models.CharField(max_length=120, unique=True, db_index=True)
    pool      = models.ForeignKey(Pool, on_delete=models.CASCADE, related_name='volumes')
    status    = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)

    bytes = models.BigIntegerField(default=0)
    files = models.IntegerField(default=0)

    first_written = models.DateTimeField(null=True, blank=True)
    last_written  = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_written']

    def __str__(self):
        return self.name
