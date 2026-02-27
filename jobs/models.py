"""Job models for backup job tracking."""
from django.db import models
from clients.models import Client


class Job(models.Model):
    """
    Backup job model.
    Mirrors Qt app BJobsModel structure.
    """

    # Job status choices (match Bareos status codes)
    STATUS_CHOICES = [
        ('T', 'Completed'),           # Terminated normally
        ('W', 'Completed with warnings'),
        ('F', 'Failed'),
        ('E', 'Error'),
        ('R', 'Running'),
        ('A', 'Aborted'),
        ('D', 'Damaged'),             # Disk full, etc.
        ('P', 'Purged'),
        ('I', 'Incomplete'),
        ('M', 'Marked to be rerun'),
        ('S', 'Sleeping'),
        ('q', 'Queued waiting for client'),
    ]

    # Job level choices (backup type)
    LEVEL_CHOICES = [
        ('F', 'Full'),
        ('I', 'Incremental'),
        ('D', 'Differential'),
        ('B', 'Base'),
        ('V', 'Virtual Full'),
        ('C', 'Catalog'),
        ('O', 'Since'),
    ]

    # Core fields
    bareos_id = models.IntegerField(unique=True, db_index=True, help_text="Bareos Job ID")
    name = models.CharField(max_length=120, db_index=True, help_text="Job name")
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='jobs')

    # Job type and level
    job_type = models.CharField(max_length=10, default='Backup',
                               help_text="Job type: Backup, Restore, Verify, etc.")
    level = models.CharField(max_length=1, choices=LEVEL_CHOICES, default='F')

    # Status
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, db_index=True)

    # Timing
    scheduled_time = models.DateTimeField(null=True, blank=True)
    actual_time = models.DateTimeField(null=True, blank=True, db_index=True)
    end_time = models.DateTimeField(null=True, blank=True)

    # Size and file counts
    bytes = models.BigIntegerField(default=0, help_text="Total bytes backed up")
    files = models.IntegerField(default=0, help_text="Total files backed up")
    errors = models.IntegerField(default=0, help_text="Number of errors")

    # Job info
    filesets = models.CharField(max_length=255, blank=True)
    pool_name = models.CharField(max_length=120, blank=True)
    storage_name = models.CharField(max_length=120, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-actual_time']
        indexes = [
            models.Index(fields=['bareos_id']),
            models.Index(fields=['status', '-actual_time']),
            models.Index(fields=['client', '-actual_time']),
            models.Index(fields=['level', '-actual_time']),
        ]

    def __str__(self):
        return f"{self.name} (ID: {self.bareos_id})"

    def get_status_display_short(self):
        """Get short readable status."""
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    def get_level_display_short(self):
        """Get short readable level."""
        return dict(self.LEVEL_CHOICES).get(self.level, self.level)

    def duration_seconds(self):
        """Get job duration in seconds."""
        if self.actual_time and self.end_time:
            return (self.end_time - self.actual_time).total_seconds()
        return None

    @property
    def duration_str(self):
        """Format duration as HH:MM:SS."""
        secs = self.duration_seconds()
        if secs is None:
            return '—'
        secs = int(secs)
        return f'{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}'

    def is_running(self):
        """Check if job is currently running."""
        return self.status == 'R'

    def is_successful(self):
        """Check if job completed successfully."""
        return self.status in ['T', 'W']

    def is_failed(self):
        """Check if job failed."""
        return self.status in ['F', 'E', 'A']


class JobFile(models.Model):
    """
    Job file list entry (for restore operations).
    Populated by BVFS queries.
    """
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='file_entries')
    path = models.TextField(help_text="Full file path")
    name = models.CharField(max_length=255, db_index=True)
    size = models.BigIntegerField(default=0)
    mod_time = models.DateTimeField(null=True, blank=True)
    is_dir = models.BooleanField(default=False)

    class Meta:
        ordering = ['path']
        verbose_name_plural = 'Job files'

    def __str__(self):
        return self.path


class JobLog(models.Model):
    """
    Job log entries (messages from Director).
    """
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='logs')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'Job logs'

    def __str__(self):
        return f"{self.job.name}: {self.message[:50]}"

