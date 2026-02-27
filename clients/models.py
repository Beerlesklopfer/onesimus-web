"""Client models for backup client tracking."""
from django.db import models


class Client(models.Model):
    """
    Backup client model.
    Represents a Bareos Client (FileDeamon).
    """

    # Client status choices
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('unknown', 'Unknown'),
        ('disabled', 'Disabled'),
        ('connecting', 'Connecting'),
    ]

    # Core fields
    bareos_id = models.IntegerField(unique=True, db_index=True, help_text="Bareos Client ID")
    name = models.CharField(max_length=120, unique=True, db_index=True, help_text="Client name")

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline',
                             db_index=True)

    # Connection info
    address = models.CharField(max_length=255, blank=True, help_text="IP address or hostname")
    port = models.IntegerField(default=9102, help_text="FileDeamon port")

    # Client info
    version = models.CharField(max_length=50, blank=True, help_text="FileDeamon version")
    uname = models.TextField(blank=True, help_text="uname output from client")

    # Backup statistics
    last_backup = models.DateTimeField(null=True, blank=True, db_index=True)
    total_bytes = models.BigIntegerField(default=0, help_text="Total bytes backed up (all time)")

    # Retention
    file_retention_days = models.IntegerField(default=60,  help_text="File retention in days")
    job_retention_days  = models.IntegerField(default=180, help_text="Job retention in days")

    # Flags
    enabled = models.BooleanField(default=True)
    auto_prune = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['status', '-last_backup']),
        ]

    def __str__(self):
        return self.name

    @property
    def os_name(self) -> str:
        """Extract OS name from uname string (e.g. 'Linux')."""
        if not self.uname:
            return ''
        return self.uname.split()[0] if self.uname.split() else ''

    def is_online(self):
        """Check if client is online."""
        return self.status == 'online'

    def is_offline(self):
        """Check if client is offline."""
        return self.status == 'offline'

    def is_disabled(self):
        """Check if client is disabled."""
        return self.status == 'disabled'

