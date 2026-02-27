# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

"""Schedule models for job scheduling."""
from django.db import models
from jobs.models import Job


class Schedule(models.Model):
    """
    Job schedule model.
    Defines when jobs should run.
    """

    # Core fields
    bareos_id = models.IntegerField(unique=True, db_index=True, help_text="Bareos Schedule ID")
    name = models.CharField(max_length=120, unique=True, db_index=True, help_text="Schedule name")

    # Associated job
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True,
                           related_name='schedules')

    # Run times (stored as JSON or cron-like format)
    # Example: {"monday": "22:00", "tuesday": "22:00", ...}
    # Will be replaced with Views/SPs querying Bareos
    run_times = models.JSONField(default=dict, blank=True, help_text="Schedule run times")

    # Flags
    enabled = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ScheduleRun(models.Model):
    """
    Record of when a scheduled job ran.
    """
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='runs')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='scheduled_runs')
    scheduled_time = models.DateTimeField(db_index=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-scheduled_time']

    def __str__(self):
        return f"{self.schedule.name}: {self.scheduled_time}"

