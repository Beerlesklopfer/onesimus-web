# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

"""Management command to populate 200 mock job records."""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from clients.models import Client
from jobs.models import Job, JobFile, JobLog

# Weighted status distribution (realistic: mostly success, few failures)
_STATUS_WEIGHTS = [
    ('T', 55),  # Completed
    ('W', 20),  # Warnings
    ('F',  8),  # Failed
    ('E',  5),  # Error
    ('A',  4),  # Aborted
    ('R',  3),  # Running (current)
    ('I',  2),  # Incomplete
    ('q',  2),  # Queued
    ('S',  1),  # Sleeping
]
_STATUSES, _STATUS_W = zip(*_STATUS_WEIGHTS)

# Weighted level distribution (incremental most common)
_LEVEL_WEIGHTS = [
    ('I', 60),  # Incremental
    ('F', 20),  # Full
    ('D', 15),  # Differential
    ('V',  5),  # Virtual Full
]
_LEVELS, _LEVEL_W = zip(*_LEVEL_WEIGHTS)

_CLIENTS = [
    # (name, address, status, version, uname)
    ('web-server-01',  '192.168.1.10', 'online',   'Bareos 23.0.3', 'Linux x86_64 GNU/Linux'),
    ('db-server-01',   '192.168.1.11', 'online',   'Bareos 23.0.3', 'Linux x86_64 GNU/Linux'),
    ('file-server-01', '192.168.1.12', 'online',   'Bareos 23.0.3', 'Linux x86_64 GNU/Linux'),
    ('mail-server-01', '192.168.1.13', 'unknown',  'Bareos 22.1.0', ''),
    ('backup-server',  '192.168.1.14', 'online',   'Bareos 23.0.3', 'Linux x86_64 GNU/Linux'),
    ('app-server-01',  '192.168.1.15', 'online',   'Bareos 21.2.0', 'Linux x86_64 GNU/Linux'),
    ('nas-storage-01', '192.168.1.20', 'offline',  'Bareos 23.0.3', 'Linux aarch64 GNU/Linux'),
    ('dev-server-01',  '192.168.1.30', 'unknown',  '',              ''),
]

_JOB_CONFIGS = [
    # (name_template, pool, storage, fileset, bytes_range, files_range, dur_range_min)
    ('Full-Backup-Daily',           'Full',        'File-SD',  'Linux-Full',     (50e9,  500e9),  (50000,  500000), (60, 480)),
    ('Incremental-Backup-Hourly',   'Incremental', 'File-SD',  'Linux-Inc',      (100e6,  5e9),   (500,    20000),  (5,  30)),
    ('Differential-Backup-Weekly',  'Differential','File-SD',  'Linux-Diff',     (5e9,   50e9),   (5000,   80000),  (20, 120)),
    ('Database-Backup-Daily',       'Full',        'Tape-SD',  'MySQL-All',      (1e9,   20e9),   (100,    5000),   (10, 60)),
    ('Mail-Backup-Daily',           'Full',        'File-SD',  'Postfix-Mail',   (500e6,  5e9),   (1000,   50000),  (5,  40)),
    ('Home-Directories-Full',       'Full',        'File-SD',  'Home-Dirs',      (20e9, 200e9),   (20000, 300000),  (30, 240)),
    ('System-Config-Backup',        'Full',        'File-SD',  'EtcBackup',      (50e6,  500e6),  (200,    5000),   (2,  15)),
    ('VMs-Full-Backup',             'Full',        'Tape-SD',  'VMware-All',     (200e9, 2000e9), (100,    1000),   (120, 720)),
    ('Logs-Incremental',            'Incremental', 'File-SD',  'Syslog-Inc',     (10e6,  1e9),    (50,     5000),   (1,  10)),
    ('Restore-Test-Verify',         'Full',        'File-SD',  'Linux-Full',     (1e9,   10e9),   (1000,   20000),  (10, 60)),
]

_LOG_MESSAGES = {
    'F': [
        'Fatal error: connection refused by client',
        'Backup failed: client timed out after 300s',
        'Fatal error: volume full, no free space',
        'Job terminated with fatal errors',
    ],
    'E': [
        'Error reading file: permission denied',
        'Backup failed with {n} errors',
        'Network error during data transfer',
        'Checksum mismatch on volume write',
    ],
    'W': [
        'Job completed with {n} warning(s)',
        'Some files could not be read (permission denied)',
        'Volume label mismatch – using override',
        'Soft link cycle detected, skipped',
    ],
    'A': [
        'Job aborted by operator',
        'Job cancelled: exceeded max run time',
        'Aborted due to director restart',
    ],
    'R': ['Job is currently running…'],
    'I': ['Job terminated – backup set is incomplete'],
}


# Mock file trees per fileset: (parent_path, name, is_dir, size_bytes)
_FILE_TREES = {
    'Linux-Full': [
        ('/etc/',           'hostname',     False, 32),
        ('/etc/',           'hosts',        False, 512),
        ('/etc/',           'fstab',        False, 1_024),
        ('/etc/',           'crontab',      False, 1_024),
        ('/etc/',           'ssh',          True,  0),
        ('/etc/ssh/',       'sshd_config',  False, 3_964),
        ('/etc/ssh/',       'ssh_config',   False, 1_650),
        ('/home/',          'admin',        True,  0),
        ('/home/admin/',    '.bashrc',      False, 3_526),
        ('/home/admin/',    '.profile',     False, 807),
        ('/home/admin/',    'backup.sh',    False, 2_048),
        ('/var/',           'log',          True,  0),
        ('/var/log/',       'syslog',       False, 10_485_760),
        ('/var/log/',       'auth.log',     False, 2_097_152),
        ('/var/log/',       'kern.log',     False, 1_048_576),
    ],
    'Linux-Inc': [
        ('/var/',           'log',          True,  0),
        ('/var/log/',       'syslog',       False, 524_288),
        ('/var/log/',       'auth.log',     False, 102_400),
        ('/home/',          'admin',        True,  0),
        ('/home/admin/',    '.bash_history', False, 8_192),
    ],
    'Linux-Diff': [
        ('/etc/',           'passwd',       False, 2_048),
        ('/etc/',           'shadow',       False, 1_024),
        ('/home/',          'admin',        True,  0),
        ('/home/admin/',    '.bashrc',      False, 3_526),
        ('/var/',           'log',          True,  0),
        ('/var/log/',       'syslog',       False, 1_048_576),
        ('/var/log/',       'dpkg.log',     False, 204_800),
    ],
    'MySQL-All': [
        ('/var/',           'lib',          True,  0),
        ('/var/lib/',       'mysql',        True,  0),
        ('/var/lib/mysql/', 'ibdata1',      False, 1_073_741_824),
        ('/var/lib/mysql/', 'ib_logfile0',  False, 104_857_600),
        ('/var/lib/mysql/', 'mysql',        True,  0),
        ('/var/lib/mysql/mysql/', 'user.MYD', False, 6_144),
        ('/var/lib/mysql/mysql/', 'db.MYD',   False, 4_096),
        ('/var/backups/',   'mysql.sql.gz', False, 52_428_800),
    ],
    'Postfix-Mail': [
        ('/var/',           'spool',        True,  0),
        ('/var/spool/',     'mail',         True,  0),
        ('/var/spool/mail/', 'admin',       False, 204_800),
        ('/var/spool/mail/', 'root',        False, 51_200),
        ('/etc/',           'postfix',      True,  0),
        ('/etc/postfix/',   'main.cf',      False, 8_192),
        ('/etc/postfix/',   'master.cf',    False, 4_096),
    ],
    'Home-Dirs': [
        ('/home/',          'user1',        True,  0),
        ('/home/user1/',    'Documents',    True,  0),
        ('/home/user1/Documents/', 'report.pdf', False, 2_097_152),
        ('/home/user1/Documents/', 'notes.txt',  False, 8_192),
        ('/home/user1/',    '.bashrc',      False, 3_526),
        ('/home/',          'user2',        True,  0),
        ('/home/user2/',    '.profile',     False, 807),
        ('/home/user2/',    'backup.tar',   False, 104_857_600),
    ],
    'EtcBackup': [
        ('/etc/',           'passwd',       False, 2_048),
        ('/etc/',           'group',        False, 1_024),
        ('/etc/',           'hosts',        False, 512),
        ('/etc/',           'fstab',        False, 1_024),
        ('/etc/',           'crontab',      False, 512),
        ('/etc/',           'ssh',          True,  0),
        ('/etc/ssh/',       'sshd_config',  False, 3_964),
        ('/etc/',           'apt',          True,  0),
        ('/etc/apt/',       'sources.list', False, 2_048),
    ],
    'VMware-All': [
        ('/vmfs/',          'volumes',      True,  0),
        ('/vmfs/volumes/',  'datastore1',   True,  0),
        ('/vmfs/volumes/datastore1/', 'ubuntu-server.vmdk', False, 107_374_182_400),
        ('/vmfs/volumes/datastore1/', 'ubuntu-server.vmx',  False, 8_192),
        ('/vmfs/volumes/datastore1/', 'debian-web.vmdk',    False, 53_687_091_200),
        ('/vmfs/volumes/datastore1/', 'debian-web.vmx',     False, 8_192),
    ],
    'Syslog-Inc': [
        ('/var/',           'log',          True,  0),
        ('/var/log/',       'syslog',       False, 104_857_600),
        ('/var/log/',       'kern.log',     False, 10_485_760),
        ('/var/log/',       'auth.log',     False, 5_242_880),
        ('/var/log/',       'daemon.log',   False, 2_097_152),
    ],
}
_FILE_TREES_DEFAULT = [
    ('/backup/',        'data',         True,  0),
    ('/backup/data/',   'backup.tar.gz', False, 524_288_000),
]


class Command(BaseCommand):
    help = 'Populate database with 200 realistic mock job records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete all existing jobs and clients before populating',
        )
        parser.add_argument(
            '--count', type=int, default=200,
            help='Number of job records to create (default: 200)',
        )

    def handle(self, *args, **options):
        if options['clear']:
            Job.objects.all().delete()
            Client.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared existing jobs and clients.'))

        now = timezone.now()

        # ── Clients ────────────────────────────────────────────────────────
        client_objs = {}
        for i, (name, addr, status, version, uname) in enumerate(_CLIENTS):
            last_conn = None
            if status == 'online':
                last_conn = now - timedelta(hours=random.randint(0, 12),
                                            minutes=random.randint(0, 59))
            obj, created = Client.objects.get_or_create(
                bareos_id=i + 1,
                defaults={
                    'name':        name,
                    'address':     addr,
                    'status':      status,
                    'version':     version,
                    'uname':       uname,
                    'last_backup': last_conn,
                },
            )
            client_objs[name] = obj
            if created:
                self.stdout.write(f'  Client: {name}')

        client_list = list(client_objs.values())

        # ── Jobs ───────────────────────────────────────────────────────────
        count = options['count']
        created_count = 0

        # Start bareos_id above any existing max
        from django.db.models import Max
        max_id = Job.objects.aggregate(Max('bareos_id'))['bareos_id__max'] or 0
        bareos_id = max_id + 1

        for _ in range(count):
            cfg = random.choice(_JOB_CONFIGS)
            name_tpl, pool, storage, fileset, bytes_rng, files_rng, dur_rng = cfg

            status = random.choices(_STATUSES, weights=_STATUS_W, k=1)[0]
            level  = random.choices(_LEVELS,   weights=_LEVEL_W,  k=1)[0]
            client = random.choice(client_list)

            # Timing: spread over the last 90 days; running/queued jobs are recent
            if status in ('R', 'q', 'S'):
                days_ago = random.uniform(0, 0.5)
            else:
                days_ago = random.uniform(0, 90)

            start = now - timedelta(days=days_ago,
                                    hours=random.randint(0, 23),
                                    minutes=random.randint(0, 59))
            dur_minutes = random.randint(*dur_rng)

            if status in ('R', 'q', 'S'):
                end = None
                elapsed = dur_minutes * 0.3          # partially done
                bytes_val = int(random.uniform(*bytes_rng) * 0.3)
                files_val = int(random.uniform(*files_rng) * 0.3)
            else:
                end = start + timedelta(minutes=dur_minutes)
                bytes_val = int(random.uniform(*bytes_rng))
                files_val = int(random.uniform(*files_rng))

            errors = 0
            if status in ('W',):
                errors = random.randint(1, 15)
            elif status in ('E',):
                errors = random.randint(5, 50)
            elif status in ('F', 'A'):
                errors = random.randint(1, 5)

            job_name = f'{name_tpl}'  # keep clean name; bareos_id makes it unique

            job, created = Job.objects.get_or_create(
                bareos_id=bareos_id,
                defaults={
                    'name':         job_name,
                    'client':       client,
                    'status':       status,
                    'level':        level,
                    'job_type':     'Backup',
                    'actual_time':  start,
                    'end_time':     end,
                    'bytes':        bytes_val,
                    'files':        files_val,
                    'errors':       errors,
                    'filesets':     fileset,
                    'pool_name':    pool,
                    'storage_name': storage,
                },
            )

            if created:
                created_count += 1
                # Add a log entry for notable statuses
                msgs = _LOG_MESSAGES.get(status)
                if msgs:
                    msg = random.choice(msgs).format(n=errors)
                    JobLog.objects.create(job=job, message=msg)

                # Add mock file entries for completed jobs
                if status in ('T', 'W'):
                    tree = _FILE_TREES.get(fileset, _FILE_TREES_DEFAULT)
                    for path, name, is_dir, size in tree:
                        actual_size = int(size * random.uniform(0.7, 1.3)) if size > 0 else 0
                        mod_dt = start - timedelta(days=random.randint(0, 30))
                        JobFile.objects.create(
                            job=job,
                            path=path,
                            name=name,
                            is_dir=is_dir,
                            size=actual_size,
                            mod_time=None if is_dir else mod_dt,
                        )

            bareos_id += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Created {created_count} new job(s) ({count} requested).'
            )
        )
