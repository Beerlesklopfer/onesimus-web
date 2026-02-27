"""Storage models for pool and volume management."""
from django.db import models


class Pool(models.Model):
    """Storage pool model."""

    # Core fields
    bareos_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=120, unique=True, db_index=True)

    # Pool settings
    use_catalog = models.BooleanField(default=True)
    pool_type = models.CharField(max_length=50, default='Backup')
    max_volumes = models.IntegerField(default=0, help_text="0 = unlimited")
    recycle_oldest_volume = models.BooleanField(default=False)
    recycle_current_volume = models.BooleanField(default=False)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Volume(models.Model):
    """Storage volume (tape/disk) model."""

    # Status choices
    STATUS_CHOICES = [
        ('Append', 'Append'),
        ('Archive', 'Archive'),
        ('Cleaning', 'Cleaning'),
        ('Disabled', 'Disabled'),
        ('Error', 'Error'),
        ('Full', 'Full'),
        ('Recycle', 'Recycle'),
        ('Purged', 'Purged'),
    ]

    # Core fields
    bareos_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=120, unique=True, db_index=True)
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE, related_name='volumes')

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)

    # Capacity
    bytes = models.BigIntegerField(default=0, help_text="Total bytes on volume")
    files = models.IntegerField(default=0, help_text="Total files on volume")

    # Metadata
    first_written = models.DateTimeField(null=True, blank=True)
    last_written = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_written']

    def __str__(self):
        return self.name

