# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

"""Management command to populate mock schedule records."""
from django.core.management.base import BaseCommand

from jobs.models import Job
from schedules.models import Schedule

# (bareos_id, schedule_name, exact_job_name, run_times)
# run_times: list of {'days': [0..6], 'at': 'HH:MM', 'level': str, 'duration_min': int}
# days: 0=Mon, 1=Tue, ..., 6=Sun
_MOCK_SCHEDULES = [
    (1, 'NightlyFull', 'Full-Backup-Daily', [
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '22:00', 'level': 'F', 'duration_min': 240},
    ]),
    (2, 'HourlyIncremental', 'Incremental-Backup-Hourly', [
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '01:00', 'level': 'I', 'duration_min': 20},
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '05:00', 'level': 'I', 'duration_min': 20},
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '09:00', 'level': 'I', 'duration_min': 20},
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '13:00', 'level': 'I', 'duration_min': 20},
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '17:00', 'level': 'I', 'duration_min': 20},
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '21:00', 'level': 'I', 'duration_min': 20},
    ]),
    (3, 'WeeklyDifferential', 'Differential-Backup-Weekly', [
        {'days': [5], 'at': '01:00', 'level': 'D', 'duration_min': 90},
    ]),
    (4, 'DatabaseNightly', 'Database-Backup-Daily', [
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '00:30', 'level': 'F', 'duration_min': 45},
    ]),
    (5, 'MailNightly', 'Mail-Backup-Daily', [
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '23:30', 'level': 'F', 'duration_min': 30},
    ]),
    (6, 'HomeWeekly', 'Home-Directories-Full', [
        {'days': [6], 'at': '03:00', 'level': 'F', 'duration_min': 180},
    ]),
    (7, 'SysConfigNightly', 'System-Config-Backup', [
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '04:00', 'level': 'F', 'duration_min': 10},
    ]),
    (8, 'VMsWeekly', 'VMs-Full-Backup', [
        {'days': [6], 'at': '04:30', 'level': 'F', 'duration_min': 480},
    ]),
    (9, 'SyslogHourly', 'Logs-Incremental', [
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '00:00', 'level': 'I', 'duration_min': 5},
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '06:00', 'level': 'I', 'duration_min': 5},
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '12:00', 'level': 'I', 'duration_min': 5},
        {'days': [0, 1, 2, 3, 4, 5, 6], 'at': '18:00', 'level': 'I', 'duration_min': 5},
    ]),
]


class Command(BaseCommand):
    help = 'Populate database with mock schedule records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete existing schedules before populating',
        )

    def handle(self, *args, **options):
        if options['clear']:
            Schedule.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared existing schedules.'))

        created_count = 0
        updated_count = 0
        for bareos_id, name, job_name, run_times in _MOCK_SCHEDULES:
            job = Job.objects.filter(name=job_name).order_by('-actual_time').first()

            obj, created = Schedule.objects.update_or_create(
                bareos_id=bareos_id,
                defaults={
                    'name':      name,
                    'job':       job,
                    'run_times': run_times,
                    'enabled':   True,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
            job_str = job.name if job else '(no matching job)'
            self.stdout.write(f'  {"+" if created else "~"} {name} → {job_str}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Created {created_count}, updated {updated_count} schedule(s).'
            )
        )
