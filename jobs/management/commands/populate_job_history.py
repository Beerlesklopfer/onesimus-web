"""Management command to populate historical job run data for Trend charts."""
import datetime as _dt
import hashlib
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from clients.models import Client
from jobs.models import Job, JobLog


# Mirror the schedule definitions from populate_mock_schedules.py.
# (job_name, at_times, days_of_week, base_dur_min, level, client_name)
# days_of_week: None = all days, [5] = Saturday only, [6] = Sunday only
_SCHEDULED_JOBS = [
    ('Full-Backup-Daily',          ['22:00'],                                  None, 240, 'F', 'file-server-01'),
    ('Incremental-Backup-Hourly',  ['01:00','05:00','09:00','13:00','17:00','21:00'], None, 20, 'I', 'file-server-01'),
    ('Differential-Backup-Weekly', ['01:00'],                                  [5],  90,  'D', 'file-server-01'),
    ('Database-Backup-Daily',      ['00:30'],                                  None, 45,  'F', 'db-server-01'),
    ('Mail-Backup-Daily',          ['23:30'],                                  None, 30,  'F', 'mail-server-01'),
    ('Home-Directories-Full',      ['03:00'],                                  [6],  180, 'F', 'file-server-01'),
    ('System-Config-Backup',       ['04:00'],                                  None, 10,  'F', 'web-server-01'),
    ('VMs-Full-Backup',            ['04:30'],                                  [6],  480, 'F', 'backup-server'),
    ('Logs-Incremental',           ['00:00','06:00','12:00','18:00'],          None, 5,   'I', 'web-server-01'),
]

# Weighted status distribution — no running/queued states in history
_STATUS_WEIGHTS = [('T', 65), ('W', 20), ('F', 8), ('E', 5), ('A', 2)]
_STATUSES, _WEIGHTS = zip(*_STATUS_WEIGHTS)
_TOTAL_WEIGHT = sum(_WEIGHTS)

# Approximate bytes/minute and files/minute by backup level
_BYTES_PER_MIN  = {'F': 450_000_000, 'I':  40_000_000, 'D': 130_000_000, 'V': 380_000_000}
_FILES_PER_MIN  = {'F':       1_200, 'I':         120, 'D':         350, 'V':         900}


# ── Seeded helpers ────────────────────────────────────────────────────────────

def _seeded_status(job_name: str, dt_key: str) -> str:
    """Deterministic status derived from MD5 of job name + datetime string."""
    digest = hashlib.md5(f'st{job_name}{dt_key}'.encode()).hexdigest()[:8]
    r = int(digest, 16) % _TOTAL_WEIGHT
    cum = 0
    for status, w in _STATUS_WEIGHTS:
        cum += w
        if r < cum:
            return status
    return 'T'


def _seeded_duration(job_name: str, dt_key: str, base_min: int) -> float:
    """Duration with realistic ±25 % noise, seeded for determinism."""
    digest = hashlib.md5(f'dur{job_name}{dt_key}'.encode()).hexdigest()[:8]
    factor = 0.75 + (int(digest, 16) % 1000) / 2000.0   # 0.75 … 1.25
    return max(1.0, round(base_min * factor, 1))


def _seeded_noise(seed_str: str) -> float:
    """Return a noise factor 0.7…1.3 for volume/file counts."""
    digest = hashlib.md5(seed_str.encode()).hexdigest()[:8]
    return 0.70 + (int(digest, 16) % 600) / 1000.0


def _fmt_elapsed(dur_min: float) -> str:
    total_s = int(dur_min * 60)
    h, rem = divmod(total_s, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f'{h} hour {m} min {s} secs'
    return f'{m} min {s} secs'


def _fmt_bytes(b: int) -> str:
    for unit, threshold in (('TB', 1_000_000_000_000), ('GB', 1_000_000_000),
                             ('MB', 1_000_000), ('KB', 1_000)):
        if b >= threshold:
            return f'{b / threshold:.2f} {unit}'
    return f'{b} B'


# ── Log message builder ───────────────────────────────────────────────────────

def _make_log_messages(
    bareos_id: int,
    job_name: str,
    level: str,
    status: str,
    client_name: str,
    start,
    end,
    dur_min: float,
    dt_key: str,
) -> list[tuple[str, object]]:
    """
    Return a list of (message, timestamp) tuples for this job run.
    Timestamps are evenly spaced between start and end.
    """
    level_label = {'F': 'Full', 'I': 'Incremental', 'D': 'Differential',
                   'V': 'VirtualFull', 'B': 'Base'}.get(level, level)
    ts0  = start.strftime('%d-%b %H:%M')
    date = start.strftime('%d-%b-%Y')
    job_instance = f'{job_name}.{start.strftime("%Y-%m-%d_%H.%M.%S")}_01'

    # ── Opening lines (always present) ──────────────────────────────────────
    msgs = [
        f'{ts0} bareos-dir JobId {bareos_id}: Start Backup JobId {bareos_id}, '
        f'Job={job_instance}',
        f'{ts0} bareos-dir JobId {bareos_id}: Using Device "File-SD" to write.',
        f'{ts0} bareos-fd  JobId {bareos_id}: Connected to Storage daemon at '
        f'storage-server:9103 with TLS',
    ]

    # ── Status-specific body ─────────────────────────────────────────────────
    if status == 'W':
        msgs.append(
            f'{ts0} bareos-fd  JobId {bareos_id}: Warning: '
            f'/proc/sys/fs/protected_hardlinks — Permission denied'
        )
        msgs.append(
            f'{ts0} bareos-fd  JobId {bareos_id}: Warning: 3 file(s) not readable; skipped.'
        )

    elif status == 'F':
        msgs.append(
            f'{ts0} bareos-dir JobId {bareos_id}: Fatal error: '
            f'connection refused by client {client_name}-fd'
        )

    elif status == 'E':
        msgs.append(
            f'{ts0} bareos-fd  JobId {bareos_id}: Error: '
            f'read error on /var/lib — Input/output error'
        )
        msgs.append(
            f'{ts0} bareos-fd  JobId {bareos_id}: Errors encountered: 7 — job continues'
        )

    elif status == 'A':
        msgs.append(
            f'{ts0} bareos-dir JobId {bareos_id}: Job cancelled by operator command.'
        )

    # ── Summary block (for completed runs) ──────────────────────────────────
    if status in ('T', 'W'):
        noise     = _seeded_noise(f'byt{job_name}{dt_key}')
        noise_f   = _seeded_noise(f'fil{job_name}{dt_key}')
        bytes_val = int(_BYTES_PER_MIN.get(level, 200_000_000) * dur_min * noise)
        files_val = int(_FILES_PER_MIN.get(level, 500) * dur_min * noise_f)
        rate_mbs  = (bytes_val / (dur_min * 60) / 1_000_000) if dur_min > 0 else 0
        term_str  = 'Backup OK' if status == 'T' else 'Backup OK -- with warnings'
        end_ts    = end.strftime('%d-%b-%Y %H:%M:%S')

        msgs.append(
            f'{ts0} bareos-dir JobId {bareos_id}: Bareos 23.0.3 (22Aug23):\n'
            f'  JobId:                  {bareos_id}\n'
            f'  Job:                    {job_instance}\n'
            f'  Backup Level:           {level_label}\n'
            f'  Client:                 {client_name}-fd\n'
            f'  Start time:             {date} {start.strftime("%H:%M:%S")}\n'
            f'  End time:               {end_ts}\n'
            f'  Elapsed time:           {_fmt_elapsed(dur_min)}\n'
            f'  FD Files Written:       {files_val:,}\n'
            f'  FD Bytes Written:       {_fmt_bytes(bytes_val)}\n'
            f'  Rate:                   {rate_mbs:.2f} MB/s\n'
            f'  Non-fatal FD errors:    {3 if status == "W" else 0}\n'
            f'  SD Errors:              0\n'
            f'  Termination:            {term_str}'
        )

    elif status in ('F', 'E'):
        msgs.append(
            f'{ts0} bareos-dir JobId {bareos_id}: '
            f'Termination:            *** Backup Error ***'
        )

    elif status == 'A':
        msgs.append(
            f'{ts0} bareos-dir JobId {bareos_id}: '
            f'Termination:            Backup Canceled'
        )

    # ── Assign timestamps spread evenly across the run duration ─────────────
    n = len(msgs)
    result = []
    for i, msg in enumerate(msgs):
        frac = i / max(n - 1, 1)
        ts   = start + timedelta(seconds=int(dur_min * 60 * frac))
        result.append((msg, ts))

    return result


# ── Management command ────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        'Populate N days of historical job run data for each scheduled job. '
        'Generates deterministic status/duration/logs from MD5 hashes so reruns are idempotent.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=120,
            help='Days of history to generate (default: 120)',
        )
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete all existing jobs with scheduled names before populating',
        )

    def handle(self, *args, **options):
        days = options['days']
        now  = timezone.now()

        if options['clear']:
            names = [j[0] for j in _SCHEDULED_JOBS]
            deleted, _ = Job.objects.filter(name__in=names).delete()
            self.stdout.write(self.style.WARNING(f'Cleared {deleted} existing history job(s).'))

        clients   = {c.name: c for c in Client.objects.all()}
        max_id    = Job.objects.aggregate(Max('bareos_id'))['bareos_id__max'] or 1000
        bareos_id = max_id + 1
        created   = 0
        skipped   = 0

        with transaction.atomic():
            for job_name, at_times, dow, base_dur, level, client_name in _SCHEDULED_JOBS:
                client = clients.get(client_name)
                self.stdout.write(f'  {job_name} …')

                for day_offset in range(days - 1, -1, -1):   # oldest → newest
                    date    = (now - timedelta(days=day_offset)).date()
                    weekday = date.weekday()

                    if dow is not None and weekday not in dow:
                        continue   # not a scheduled day

                    for at_str in at_times:
                        h, m = map(int, at_str.split(':'))
                        naive_start = _dt.datetime(date.year, date.month, date.day, h, m, 0)
                        start = timezone.make_aware(naive_start)

                        if start >= now:
                            continue   # don't create future runs

                        dt_key  = start.strftime('%Y%m%d%H%M')
                        status  = _seeded_status(job_name, dt_key)
                        dur_min = _seeded_duration(job_name, dt_key, base_dur)
                        end     = start + timedelta(minutes=dur_min)

                        if Job.objects.filter(name=job_name, actual_time=start).exists():
                            skipped += 1
                            continue

                        job = Job.objects.create(
                            bareos_id    = bareos_id,
                            name         = job_name,
                            client       = client,
                            status       = status,
                            level        = level,
                            job_type     = 'Backup',
                            actual_time  = start,
                            end_time     = end,
                            bytes        = 0,
                            files        = 0,
                            errors       = (1 if status in ('W', 'E') else 0),
                            pool_name    = 'Default',
                            storage_name = 'File-SD',
                        )

                        # Create log entries with timestamps spread across the run
                        log_entries = _make_log_messages(
                            bareos_id, job_name, level, status,
                            client_name or 'unknown', start, end, dur_min, dt_key,
                        )
                        log_objs = JobLog.objects.bulk_create(
                            [JobLog(job=job, message=msg) for msg, _ in log_entries]
                        )
                        # Fix timestamps (auto_now_add → actual run time)
                        for log_obj, (_, ts) in zip(log_objs, log_entries):
                            log_obj.timestamp = ts
                        JobLog.objects.bulk_update(log_objs, ['timestamp'])

                        bareos_id += 1
                        created   += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Created {created} run(s) with log entries'
                + (f', skipped {skipped} duplicate(s).' if skipped else '.')
            )
        )

        # Re-link Schedule.job FKs — populate_job_history --clear sets them to NULL
        # (on_delete=SET_NULL) so we always refresh them after creating new jobs.
        try:
            from schedules.models import Schedule
            relinked = 0
            for sched in Schedule.objects.all():
                # Derive job name from existing link or by matching schedule name
                job_name_hint = sched.job.name if sched.job else None
                if job_name_hint is None:
                    # Map well-known schedule names → job names
                    _SCHED_JOB = {
                        'NightlyFull':        'Full-Backup-Daily',
                        'HourlyIncremental':  'Incremental-Backup-Hourly',
                        'WeeklyDifferential': 'Differential-Backup-Weekly',
                        'DatabaseNightly':    'Database-Backup-Daily',
                        'MailNightly':        'Mail-Backup-Daily',
                        'HomeWeekly':         'Home-Directories-Full',
                        'SysConfigNightly':   'System-Config-Backup',
                        'VMsWeekly':          'VMs-Full-Backup',
                        'SyslogHourly':       'Logs-Incremental',
                    }
                    job_name_hint = _SCHED_JOB.get(sched.name)
                if not job_name_hint:
                    continue
                latest = Job.objects.filter(name=job_name_hint).order_by('-actual_time').first()
                if latest and sched.job_id != latest.id:
                    sched.job = latest
                    sched.save(update_fields=['job'])
                    relinked += 1
            if relinked:
                self.stdout.write(self.style.SUCCESS(f'Re-linked {relinked} schedule(s) to new jobs.'))
        except Exception:
            pass  # schedules app may not be installed in all environments
