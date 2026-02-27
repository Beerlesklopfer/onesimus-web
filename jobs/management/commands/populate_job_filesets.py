"""Management command to populate enterprise fileset data (JobFile) for backup jobs.

Each entry: (parent_path, name, is_dir, min_bytes, max_bytes, volatility)
  volatility: 'H' = high  → Full + Differential + Incremental
              'M' = medium → Full + Differential only
              'L' = low    → Full only (configs, binaries)
  is_dir=True: min_bytes=max_bytes=0

JobFile.path  = parent directory of the entry (always ends with /)
JobFile.name  = filename or directory name
JobFile.is_dir, .size, .mod_time as usual
"""
import hashlib
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from jobs.models import Job, JobFile


# ── Volatility → backup levels that include this file ────────────────────────
_LEVEL_INCLUDE = {
    'F': {'H', 'M', 'L'},
    'D': {'H', 'M'},
    'I': {'H'},
    'V': {'H', 'M', 'L'},
    'B': {'H', 'M', 'L'},
    'C': {'H'},
}

# ── Job → client mapping ──────────────────────────────────────────────────────
_JOB_CLIENT = {
    'Full-Backup-Daily':          'file-server-01',
    'Incremental-Backup-Hourly':  'file-server-01',
    'Differential-Backup-Weekly': 'file-server-01',
    'Database-Backup-Daily':      'db-server-01',
    'Mail-Backup-Daily':          'mail-server-01',
    'Home-Directories-Full':      'file-server-01',
    'System-Config-Backup':       'web-server-01',
    'VMs-Full-Backup':            'backup-server',
    'Logs-Incremental':           'web-server-01',
}

# ── Fileset names per job ─────────────────────────────────────────────────────
_JOB_FILESET = {
    'Full-Backup-Daily':          'LinuxHome,SharedStorage,NFS-Exports',
    'Incremental-Backup-Hourly':  'LinuxHome,SharedStorage',
    'Differential-Backup-Weekly': 'LinuxHome,SharedStorage,NFS-Exports',
    'Database-Backup-Daily':      'MySQL-Catalog,MySQL-Config',
    'Mail-Backup-Daily':          'Mailboxes,Postfix-Config,Dovecot-Config',
    'Home-Directories-Full':      'LinuxHome',
    'System-Config-Backup':       'NginxConfig,SSL-Certs,WebRoot',
    'VMs-Full-Backup':            'BareosDB,BareosConfig,BareosBin',
    'Logs-Incremental':           'NginxLogs,SystemLogs',
}

# ── Enterprise filesystem templates ──────────────────────────────────────────
# (parent_path, name, is_dir, min_bytes, max_bytes, volatility)
# is_dir=True → size=0 always

_FS_FILE_SERVER = [
    # /home/users/alice/
    ('/home/',                              'users',                True,  0,              0,              'L'),
    ('/home/users/',                        'alice',                True,  0,              0,              'L'),
    ('/home/users/alice/',                  'Documents',            True,  0,              0,              'M'),
    ('/home/users/alice/Documents/',        'Q1-Report.docx',       False, 80_000,         2_000_000,      'M'),
    ('/home/users/alice/Documents/',        'Q2-Report.docx',       False, 80_000,         2_000_000,      'M'),
    ('/home/users/alice/Documents/',        'Budget-2025.xlsx',     False, 150_000,        5_000_000,      'M'),
    ('/home/users/alice/Documents/',        'Presentation.pptx',    False, 800_000,       15_000_000,      'M'),
    ('/home/users/alice/Documents/',        'Project-Notes.odt',    False, 30_000,        400_000,         'H'),
    ('/home/users/alice/',                  'Pictures',             True,  0,              0,              'L'),
    ('/home/users/alice/Pictures/',         'team-offsite-2024.jpg',False, 2_000_000,      8_000_000,      'L'),
    ('/home/users/alice/Pictures/',         'conference-2025.jpg',  False, 2_000_000,      8_000_000,      'M'),
    ('/home/users/alice/Pictures/',         'profile.png',          False, 400_000,        2_000_000,      'L'),
    ('/home/users/alice/',                  'Downloads',            True,  0,              0,              'M'),
    ('/home/users/alice/Downloads/',        'ubuntu-24.04.iso',     False, 1_200_000_000, 2_000_000_000,  'L'),
    ('/home/users/alice/Downloads/',        'office-update.zip',    False, 50_000_000,   200_000_000,     'M'),
    ('/home/users/alice/',                  '.bashrc',              False, 3_000,          10_000,         'L'),
    ('/home/users/alice/',                  '.bash_history',        False, 20_000,        200_000,         'H'),
    ('/home/users/alice/',                  '.ssh',                 True,  0,              0,              'L'),
    ('/home/users/alice/.ssh/',             'authorized_keys',      False, 500,            5_000,          'L'),
    ('/home/users/alice/.ssh/',             'id_rsa.pub',           False, 700,            3_000,          'L'),
    # /home/users/bob/
    ('/home/users/',                        'bob',                  True,  0,              0,              'L'),
    ('/home/users/bob/',                    'Documents',            True,  0,              0,              'M'),
    ('/home/users/bob/Documents/',          'Project-Spec-v3.docx', False, 200_000,       4_000_000,      'M'),
    ('/home/users/bob/Documents/',          'Meeting-Notes.odt',    False, 80_000,        800_000,         'H'),
    ('/home/users/bob/Documents/',          'roadmap-2025.xlsx',    False, 300_000,       6_000_000,      'M'),
    ('/home/users/bob/',                    'code',                 True,  0,              0,              'M'),
    ('/home/users/bob/code/',               'webapp',               True,  0,              0,              'M'),
    ('/home/users/bob/code/webapp/',        'main.py',              False, 20_000,        500_000,         'H'),
    ('/home/users/bob/code/webapp/',        'models.py',            False, 30_000,        800_000,         'H'),
    ('/home/users/bob/code/webapp/',        'views.py',             False, 25_000,        600_000,         'H'),
    ('/home/users/bob/code/webapp/',        'config.yml',           False, 2_000,         20_000,          'M'),
    ('/home/users/bob/code/webapp/',        'requirements.txt',     False, 1_000,          8_000,          'M'),
    ('/home/users/bob/',                    '.gitconfig',           False, 500,            3_000,          'L'),
    ('/home/users/bob/',                    '.bash_history',        False, 30_000,        300_000,         'H'),
    # /home/users/charlie/
    ('/home/users/',                        'charlie',              True,  0,              0,              'L'),
    ('/home/users/charlie/',                'Documents',            True,  0,              0,              'M'),
    ('/home/users/charlie/Documents/',      'Annual-Review-2024.pdf',False,400_000,       8_000_000,      'L'),
    ('/home/users/charlie/Documents/',      'SLA-Template.docx',    False, 80_000,        1_500_000,      'L'),
    ('/home/users/charlie/Documents/',      'Incident-Report.docx', False, 60_000,        800_000,         'M'),
    ('/home/users/charlie/',                'scripts',              True,  0,              0,              'M'),
    ('/home/users/charlie/scripts/',        'nightly-backup.sh',    False, 3_000,         25_000,          'M'),
    ('/home/users/charlie/scripts/',        'monitor-disk.py',      False, 8_000,         60_000,          'H'),
    ('/home/users/charlie/scripts/',        'deploy-prod.sh',       False, 5_000,         40_000,          'M'),
    ('/home/users/charlie/scripts/',        'rotate-logs.sh',       False, 2_000,         15_000,          'H'),
    # /home/users/diana/
    ('/home/users/',                        'diana',                True,  0,              0,              'L'),
    ('/home/users/diana/',                  'Documents',            True,  0,              0,              'M'),
    ('/home/users/diana/Documents/',        'HR-Policy-2025.pdf',   False, 600_000,       9_000_000,      'M'),
    ('/home/users/diana/Documents/',        'Onboarding-Guide.docx',False, 300_000,       4_000_000,      'L'),
    ('/home/users/diana/Documents/',        'Employee-List.xlsx',   False, 400_000,       6_000_000,      'H'),
    ('/home/users/diana/',                  'Confidential',         True,  0,              0,              'M'),
    ('/home/users/diana/Confidential/',     'Salary-Review-2025.xlsx',False,500_000,      8_000_000,      'M'),
    ('/home/users/diana/Confidential/',     'Contracts-Q1-2025.zip',False,3_000_000,     40_000_000,      'M'),
    # /shared/projects/
    ('/shared/',                            'projects',             True,  0,              0,              'L'),
    ('/shared/projects/',                   'project-alpha',        True,  0,              0,              'M'),
    ('/shared/projects/project-alpha/',     'README.md',            False, 8_000,         80_000,          'H'),
    ('/shared/projects/project-alpha/',     'design-v4.drawio',     False, 200_000,       3_000_000,      'M'),
    ('/shared/projects/project-alpha/',     'spec-v2.pdf',          False, 800_000,      15_000_000,      'M'),
    ('/shared/projects/project-alpha/',     'backlog.xlsx',         False, 150_000,       2_000_000,      'H'),
    ('/shared/projects/',                   'project-beta',         True,  0,              0,              'M'),
    ('/shared/projects/project-beta/',      'architecture.pdf',     False, 1_000_000,    18_000_000,      'L'),
    ('/shared/projects/project-beta/',      'tasks.xlsx',           False, 200_000,       3_000_000,      'H'),
    ('/shared/projects/project-beta/',      'requirements.docx',    False, 120_000,       2_000_000,      'M'),
    # /shared/finance/
    ('/shared/',                            'finance',              True,  0,              0,              'L'),
    ('/shared/finance/',                    'invoices',             True,  0,              0,              'H'),
    ('/shared/finance/invoices/',           'INV-2025-001.pdf',     False, 80_000,        400_000,         'H'),
    ('/shared/finance/invoices/',           'INV-2025-002.pdf',     False, 80_000,        400_000,         'H'),
    ('/shared/finance/invoices/',           'INV-2025-003.pdf',     False, 80_000,        400_000,         'H'),
    ('/shared/finance/invoices/',           'INV-2025-004.pdf',     False, 80_000,        400_000,         'H'),
    ('/shared/finance/',                    'budgets',              True,  0,              0,              'M'),
    ('/shared/finance/budgets/',            'Budget-FY2025.xlsx',   False, 400_000,       7_000_000,      'M'),
    ('/shared/finance/budgets/',            'Forecast-Q2-2025.xlsx',False, 300_000,       5_000_000,      'H'),
    ('/shared/finance/budgets/',            'Actuals-Jan.xlsx',     False, 250_000,       4_000_000,      'H'),
    # /shared/hr/
    ('/shared/',                            'hr',                   True,  0,              0,              'L'),
    ('/shared/hr/',                         'contracts',            True,  0,              0,              'M'),
    ('/shared/hr/contracts/',               'contract-alice.pdf',   False, 300_000,       3_000_000,      'L'),
    ('/shared/hr/contracts/',               'contract-bob.pdf',     False, 300_000,       3_000_000,      'L'),
    ('/shared/hr/contracts/',               'contract-charlie.pdf', False, 300_000,       3_000_000,      'L'),
    ('/shared/hr/contracts/',               'contract-diana.pdf',   False, 300_000,       3_000_000,      'L'),
    ('/shared/hr/',                         'payroll',              True,  0,              0,              'H'),
    ('/shared/hr/payroll/',                 'payroll-2025-01.xlsx', False, 400_000,       6_000_000,      'H'),
    ('/shared/hr/payroll/',                 'payroll-2025-02.xlsx', False, 400_000,       6_000_000,      'H'),
    ('/shared/hr/payroll/',                 'payroll-2025-03.xlsx', False, 400_000,       6_000_000,      'H'),
    # /srv/nfs/
    ('/srv/',                               'nfs',                  True,  0,              0,              'L'),
    ('/srv/nfs/',                           'exports',              True,  0,              0,              'L'),
    ('/srv/nfs/exports/',                   'company-data',         True,  0,              0,              'M'),
    ('/srv/nfs/exports/company-data/',      'catalog.db',           False, 80_000_000,   800_000_000,     'H'),
    ('/srv/nfs/exports/company-data/',      'assets.tar',           False, 500_000_000, 5_000_000_000,    'M'),
    ('/srv/nfs/exports/company-data/',      'index.db',             False, 10_000_000,   100_000_000,     'H'),
]

_FS_DB_SERVER = [
    ('/etc/',                               'mysql',                True,  0,              0,              'L'),
    ('/etc/mysql/',                         'my.cnf',               False, 4_000,         20_000,          'L'),
    ('/etc/mysql/',                         'conf.d',               True,  0,              0,              'L'),
    ('/etc/mysql/conf.d/',                  'innodb.cnf',           False, 1_500,          8_000,          'L'),
    ('/etc/mysql/conf.d/',                  'performance.cnf',      False, 2_000,         12_000,          'M'),
    ('/etc/mysql/conf.d/',                  'binlog.cnf',           False, 1_000,          5_000,          'L'),
    ('/var/lib/',                           'mysql',                True,  0,              0,              'H'),
    ('/var/lib/mysql/',                     'production',           True,  0,              0,              'H'),
    ('/var/lib/mysql/production/',          'customers.ibd',        False, 800_000_000,  8_000_000_000,   'H'),
    ('/var/lib/mysql/production/',          'customers.frm',        False, 12_000,        80_000,          'L'),
    ('/var/lib/mysql/production/',          'orders.ibd',           False, 2_000_000_000,20_000_000_000,  'H'),
    ('/var/lib/mysql/production/',          'orders.frm',           False, 12_000,        80_000,          'L'),
    ('/var/lib/mysql/production/',          'order_items.ibd',      False, 1_000_000_000,10_000_000_000,  'H'),
    ('/var/lib/mysql/production/',          'products.ibd',         False, 400_000_000,  4_000_000_000,   'H'),
    ('/var/lib/mysql/production/',          'products.frm',         False, 12_000,        80_000,          'L'),
    ('/var/lib/mysql/production/',          'users.ibd',            False, 150_000_000,  1_500_000_000,   'H'),
    ('/var/lib/mysql/production/',          'users.frm',            False, 12_000,        80_000,          'L'),
    ('/var/lib/mysql/production/',          'audit_log.ibd',        False, 200_000_000,  2_000_000_000,   'H'),
    ('/var/lib/mysql/',                     'analytics',            True,  0,              0,              'H'),
    ('/var/lib/mysql/analytics/',           'events.ibd',           False, 3_000_000_000,30_000_000_000,  'H'),
    ('/var/lib/mysql/analytics/',           'sessions.ibd',         False, 800_000_000,  8_000_000_000,   'H'),
    ('/var/lib/mysql/analytics/',           'reports.ibd',          False, 300_000_000,  3_000_000_000,   'M'),
    ('/var/lib/mysql/analytics/',           'pageviews.ibd',        False, 500_000_000,  5_000_000_000,   'H'),
    ('/var/lib/mysql/',                     'staging',              True,  0,              0,              'M'),
    ('/var/lib/mysql/staging/',             'customers.ibd',        False, 80_000_000,   800_000_000,     'M'),
    ('/var/lib/mysql/staging/',             'orders.ibd',           False, 150_000_000,  1_500_000_000,   'M'),
    ('/var/lib/mysql/',                     'ibdata1',              False, 2_000_000_000,20_000_000_000,  'H'),
    ('/var/lib/mysql/',                     'ib_logfile0',          False, 512_000_000,  2_048_000_000,   'H'),
    ('/var/lib/mysql/',                     'ib_logfile1',          False, 512_000_000,  2_048_000_000,   'H'),
    ('/var/lib/mysql/',                     'mysql-bin.000001',     False, 100_000_000,  1_000_000_000,   'H'),
    ('/var/lib/mysql/',                     'mysql-bin.000002',     False, 100_000_000,  1_000_000_000,   'H'),
    ('/var/log/',                           'mysql',                True,  0,              0,              'H'),
    ('/var/log/mysql/',                     'mysql.log',            False, 20_000_000,   500_000_000,     'H'),
    ('/var/log/mysql/',                     'mysql-slow.log',       False, 10_000_000,   300_000_000,     'H'),
    ('/var/log/mysql/',                     'error.log',            False, 2_000_000,     80_000_000,     'H'),
    ('/var/log/mysql/',                     'mysql-bin.index',      False, 1_000,         10_000,          'H'),
]

_FS_MAIL_SERVER = [
    ('/etc/',                               'postfix',              True,  0,              0,              'L'),
    ('/etc/postfix/',                        'main.cf',              False, 8_000,         40_000,          'L'),
    ('/etc/postfix/',                        'master.cf',            False, 6_000,         25_000,          'L'),
    ('/etc/postfix/',                        'transport',            False, 3_000,         15_000,          'M'),
    ('/etc/postfix/',                        'virtual',              False, 8_000,         80_000,          'M'),
    ('/etc/postfix/',                        'sasl',                 True,  0,              0,              'L'),
    ('/etc/postfix/sasl/',                   'smtpd.conf',           False, 1_000,          5_000,          'L'),
    ('/etc/',                               'dovecot',              True,  0,              0,              'L'),
    ('/etc/dovecot/',                        'dovecot.conf',         False, 6_000,         35_000,          'L'),
    ('/etc/dovecot/',                        'conf.d',               True,  0,              0,              'L'),
    ('/etc/dovecot/conf.d/',                 '10-auth.conf',         False, 4_000,         18_000,          'L'),
    ('/etc/dovecot/conf.d/',                 '10-mail.conf',         False, 4_000,         18_000,          'L'),
    ('/etc/dovecot/conf.d/',                 '10-ssl.conf',          False, 3_000,         12_000,          'L'),
    ('/etc/dovecot/conf.d/',                 '90-quota.conf',        False, 2_000,          8_000,          'L'),
    ('/var/mail/',                           'users',                True,  0,              0,              'H'),
    ('/var/mail/users/',                     'alice',                True,  0,              0,              'H'),
    ('/var/mail/users/alice/',               'Inbox',                True,  0,              0,              'H'),
    ('/var/mail/users/alice/Inbox/',         '0001.eml',             False, 15_000,        600_000,         'H'),
    ('/var/mail/users/alice/Inbox/',         '0002.eml',             False, 15_000,        600_000,         'H'),
    ('/var/mail/users/alice/Inbox/',         '0003.eml',             False, 15_000,        600_000,         'H'),
    ('/var/mail/users/alice/Inbox/',         '0004.eml',             False, 15_000,        600_000,         'H'),
    ('/var/mail/users/alice/Inbox/',         '0005.eml',             False, 15_000,        600_000,         'H'),
    ('/var/mail/users/alice/',               'Sent',                 True,  0,              0,              'H'),
    ('/var/mail/users/alice/Sent/',          '0001.eml',             False, 8_000,         250_000,         'H'),
    ('/var/mail/users/alice/Sent/',          '0002.eml',             False, 8_000,         250_000,         'H'),
    ('/var/mail/users/alice/',               'Archive',              True,  0,              0,              'M'),
    ('/var/mail/users/alice/Archive/',       '2024-Q4.mbox',         False, 50_000_000,   500_000_000,     'M'),
    ('/var/mail/users/',                     'bob',                  True,  0,              0,              'H'),
    ('/var/mail/users/bob/',                 'Inbox',                True,  0,              0,              'H'),
    ('/var/mail/users/bob/Inbox/',           '0001.eml',             False, 15_000,        600_000,         'H'),
    ('/var/mail/users/bob/Inbox/',           '0002.eml',             False, 15_000,        600_000,         'H'),
    ('/var/mail/users/bob/Inbox/',           '0003.eml',             False, 15_000,        600_000,         'H'),
    ('/var/mail/users/bob/',                 'Sent',                 True,  0,              0,              'H'),
    ('/var/mail/users/bob/Sent/',            '0001.eml',             False, 8_000,         250_000,         'H'),
    ('/var/mail/users/',                     'charlie',              True,  0,              0,              'H'),
    ('/var/mail/users/charlie/',             'Inbox',                True,  0,              0,              'H'),
    ('/var/mail/users/charlie/Inbox/',       '0001.eml',             False, 15_000,        600_000,         'H'),
    ('/var/mail/users/charlie/Inbox/',       '0002.eml',             False, 15_000,        600_000,         'H'),
    ('/var/mail/users/charlie/',             'Drafts',               True,  0,              0,              'H'),
    ('/var/mail/users/charlie/Drafts/',      '0001.eml',             False, 10_000,        300_000,         'H'),
    ('/var/mail/users/',                     'postmaster',           True,  0,              0,              'M'),
    ('/var/mail/users/postmaster/',          'Inbox',                True,  0,              0,              'H'),
    ('/var/mail/users/postmaster/Inbox/',    'bounce-001.eml',       False, 5_000,          60_000,         'H'),
    ('/var/mail/users/postmaster/Inbox/',    'bounce-002.eml',       False, 5_000,          60_000,         'H'),
    ('/var/log/',                            'mail.log',             False, 20_000_000,   600_000_000,     'H'),
    ('/var/log/',                            'mail.err',             False, 200_000,       8_000_000,      'H'),
    ('/var/spool/',                          'postfix',              True,  0,              0,              'M'),
    ('/var/spool/postfix/',                  'queue',                True,  0,              0,              'H'),
    ('/var/spool/postfix/queue/',            'incoming',             True,  0,              0,              'H'),
    ('/var/spool/postfix/queue/',            'active',               True,  0,              0,              'H'),
    ('/var/spool/postfix/queue/',            'deferred',             True,  0,              0,              'H'),
    ('/var/spool/postfix/queue/',            'bounce',               True,  0,              0,              'H'),
]

_FS_WEB_SERVER = [
    ('/etc/',                                   'nginx',                True,  0,             0,             'L'),
    ('/etc/nginx/',                             'nginx.conf',           False, 6_000,         25_000,        'L'),
    ('/etc/nginx/',                             'mime.types',           False, 8_000,         40_000,        'L'),
    ('/etc/nginx/',                             'sites-available',      True,  0,             0,             'L'),
    ('/etc/nginx/sites-available/',             'default',              False, 3_000,         12_000,        'L'),
    ('/etc/nginx/sites-available/',             'app.example.com',      False, 4_000,         18_000,        'M'),
    ('/etc/nginx/sites-available/',             'api.example.com',      False, 3_000,         15_000,        'M'),
    ('/etc/nginx/sites-available/',             'monitoring.example.com',False,2_000,          8_000,        'L'),
    ('/etc/nginx/',                             'sites-enabled',        True,  0,             0,             'M'),
    ('/etc/nginx/sites-enabled/',               'app.example.com',      False, 300,            1_500,        'M'),
    ('/etc/nginx/sites-enabled/',               'api.example.com',      False, 300,            1_500,        'M'),
    ('/etc/nginx/',                             'conf.d',               True,  0,             0,             'L'),
    ('/etc/nginx/conf.d/',                      'gzip.conf',            False, 1_000,          5_000,        'L'),
    ('/etc/nginx/conf.d/',                      'ssl-params.conf',      False, 2_000,          8_000,        'L'),
    ('/etc/',                                   'ssl',                  True,  0,             0,             'L'),
    ('/etc/ssl/',                               'certs',                True,  0,             0,             'L'),
    ('/etc/ssl/certs/',                         'example.com.crt',      False, 2_500,         12_000,        'L'),
    ('/etc/ssl/certs/',                         'intermediate-ca.crt',  False, 3_000,         15_000,        'L'),
    ('/etc/ssl/certs/',                         'ca-bundle.crt',        False, 250_000,       1_200_000,     'L'),
    ('/etc/ssl/',                               'private',              True,  0,             0,             'L'),
    ('/etc/ssl/private/',                       'example.com.key',      False, 1_700,          8_000,        'L'),
    ('/var/www/',                               'html',                 True,  0,             0,             'M'),
    ('/var/www/html/',                          'index.html',           False, 12_000,        120_000,       'M'),
    ('/var/www/html/',                          'favicon.ico',          False, 5_000,          60_000,       'L'),
    ('/var/www/',                               'app.example.com',      True,  0,             0,             'M'),
    ('/var/www/app.example.com/',               'public',               True,  0,             0,             'H'),
    ('/var/www/app.example.com/public/',        'index.php',            False, 8_000,         80_000,        'M'),
    ('/var/www/app.example.com/public/',        'app.js',               False, 800_000,      8_000_000,      'M'),
    ('/var/www/app.example.com/public/',        'app.js.map',           False, 2_000_000,    20_000_000,     'M'),
    ('/var/www/app.example.com/public/',        'styles.css',           False, 200_000,      2_500_000,      'M'),
    ('/var/www/app.example.com/',               'config',               True,  0,             0,             'M'),
    ('/var/www/app.example.com/config/',        'database.php',         False, 4_000,         25_000,        'M'),
    ('/var/www/app.example.com/config/',        'app.php',              False, 6_000,         40_000,        'M'),
    ('/var/www/app.example.com/config/',        '.env',                 False, 2_000,         10_000,        'M'),
    ('/var/www/app.example.com/',               'storage',              True,  0,             0,             'H'),
    ('/var/www/app.example.com/storage/',       'logs',                 True,  0,             0,             'H'),
    ('/var/www/app.example.com/storage/logs/',  'laravel.log',          False, 10_000_000,  200_000_000,    'H'),
    ('/var/www/app.example.com/storage/logs/',  'worker.log',           False, 2_000_000,    40_000_000,    'H'),
    ('/var/www/app.example.com/storage/',       'uploads',              True,  0,             0,             'H'),
    ('/var/www/app.example.com/storage/uploads/','img-report-001.jpg',  False, 800_000,      6_000_000,     'H'),
    ('/var/www/app.example.com/storage/uploads/','img-report-002.jpg',  False, 800_000,      6_000_000,     'H'),
    ('/var/www/app.example.com/storage/uploads/','export-2025-02.pdf',  False, 400_000,      5_000_000,     'H'),
    ('/var/log/',                               'nginx',                True,  0,             0,             'H'),
    ('/var/log/nginx/',                         'access.log',           False, 100_000_000, 3_000_000_000,  'H'),
    ('/var/log/nginx/',                         'error.log',            False, 2_000_000,    80_000_000,    'H'),
    ('/var/log/nginx/',                         'access.log.1',         False, 80_000_000,  2_000_000_000,  'M'),
    ('/var/log/',                               'php8.2-fpm.log',       False, 5_000_000,   150_000_000,    'H'),
    ('/var/log/',                               'syslog',               False, 10_000_000,  400_000_000,    'H'),
]

_FS_BACKUP_SERVER = [
    ('/etc/',                                   'bareos',               True,  0,             0,             'L'),
    ('/etc/bareos/',                            'bareos-dir.conf',      False, 15_000,        120_000,       'L'),
    ('/etc/bareos/',                            'bareos-sd.conf',       False, 8_000,          60_000,       'L'),
    ('/etc/bareos/',                            'bareos-fd.conf',       False, 5_000,          30_000,       'L'),
    ('/etc/bareos/',                            'bconsole.conf',        False, 3_000,          20_000,       'L'),
    ('/etc/bareos/',                            'bareos-dir.d',         True,  0,             0,             'L'),
    ('/etc/bareos/bareos-dir.d/',               'client',               True,  0,             0,             'L'),
    ('/etc/bareos/bareos-dir.d/client/',        'file-server-01.conf',  False, 3_000,         15_000,        'L'),
    ('/etc/bareos/bareos-dir.d/client/',        'db-server-01.conf',    False, 3_000,         15_000,        'L'),
    ('/etc/bareos/bareos-dir.d/client/',        'mail-server-01.conf',  False, 3_000,         15_000,        'L'),
    ('/etc/bareos/bareos-dir.d/client/',        'web-server-01.conf',   False, 3_000,         15_000,        'L'),
    ('/etc/bareos/bareos-dir.d/',               'schedule',             True,  0,             0,             'L'),
    ('/etc/bareos/bareos-dir.d/schedule/',      'WeeklyCycle.conf',     False, 3_000,         12_000,        'L'),
    ('/etc/bareos/bareos-dir.d/schedule/',      'MonthlyCycle.conf',    False, 2_000,         10_000,        'L'),
    ('/etc/bareos/bareos-dir.d/',               'job',                  True,  0,             0,             'M'),
    ('/etc/bareos/bareos-dir.d/job/',           'Full-Backup.conf',     False, 4_000,         20_000,        'M'),
    ('/etc/bareos/bareos-dir.d/job/',           'Incremental.conf',     False, 4_000,         20_000,        'M'),
    ('/etc/bareos/bareos-dir.d/',               'fileset',              True,  0,             0,             'M'),
    ('/etc/bareos/bareos-dir.d/fileset/',       'LinuxHome.conf',       False, 5_000,         25_000,        'M'),
    ('/etc/bareos/bareos-dir.d/fileset/',       'MySQL-Catalog.conf',   False, 4_000,         18_000,        'M'),
    ('/etc/bareos/bareos-dir.d/fileset/',       'WebRoot.conf',         False, 4_000,         18_000,        'M'),
    ('/var/lib/',                               'bareos',               True,  0,             0,             'H'),
    ('/var/lib/bareos/',                        'bareos.db',            False, 500_000_000, 8_000_000_000,  'H'),
    ('/var/lib/bareos/',                        'bareos.db-wal',        False, 20_000_000,  400_000_000,    'H'),
    ('/var/lib/bareos/',                        'bareos.db-shm',        False, 32_000,       128_000,        'H'),
    ('/opt/',                                   'bareos',               True,  0,             0,             'L'),
    ('/opt/bareos/',                            'bin',                  True,  0,             0,             'L'),
    ('/opt/bareos/bin/',                        'bareos-dir',           False, 8_000_000,    30_000_000,     'L'),
    ('/opt/bareos/bin/',                        'bareos-sd',            False, 8_000_000,    30_000_000,     'L'),
    ('/opt/bareos/bin/',                        'bareos-fd',            False, 6_000_000,    20_000_000,     'L'),
    ('/opt/bareos/',                            'scripts',              True,  0,             0,             'M'),
    ('/opt/bareos/scripts/',                    'cleanup-volumes.sh',   False, 4_000,         30_000,        'M'),
    ('/opt/bareos/scripts/',                    'alert-on-failure.sh',  False, 4_000,         30_000,        'M'),
    ('/opt/bareos/scripts/',                    'prune-catalog.sh',     False, 3_000,         20_000,        'M'),
    ('/var/log/',                               'bareos',               True,  0,             0,             'H'),
    ('/var/log/bareos/',                        'bareos.log',           False, 100_000_000, 4_000_000_000,  'H'),
    ('/var/log/bareos/',                        'bareos-audit.log',     False, 10_000_000,  400_000_000,    'H'),
    ('/var/log/bareos/',                        'bareos-sd.log',        False, 20_000_000,  800_000_000,    'H'),
]

_FS = {
    'file-server-01': _FS_FILE_SERVER,
    'db-server-01':   _FS_DB_SERVER,
    'mail-server-01': _FS_MAIL_SERVER,
    'web-server-01':  _FS_WEB_SERVER,
    'backup-server':  _FS_BACKUP_SERVER,
}


# ── Seeded helpers ────────────────────────────────────────────────────────────

def _md5int(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)


def _seeded_size(seed: str, lo: int, hi: int) -> int:
    if lo >= hi:
        return lo
    return lo + _md5int(seed) % (hi - lo + 1)


def _seeded_mtime(seed: str, job_start, level: str):
    """Return a realistic mod_time before job_start based on backup level."""
    r = _md5int(seed) % 100_000
    if level == 'I':
        delta = timedelta(seconds=int(r * 86_400 / 100_000))      # 0–24 h
    elif level == 'D':
        delta = timedelta(seconds=int(r * 7 * 86_400 / 100_000))  # 0–7 d
    else:                                                           # F, V, B
        delta = timedelta(seconds=int(r * 365 * 86_400 / 100_000))# 0–1 year
    return job_start - delta


def _include(seed: str, volatility: str, level: str) -> bool:
    """Return True if this file should appear in this backup level."""
    if volatility in _LEVEL_INCLUDE.get(level, {'H', 'M', 'L'}):
        return True
    # ±8 % noise: occasionally a low-volatility file sneaks into an Incremental
    return _md5int('noise' + seed) % 100 < 8


# ── Management command ────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        'Populate enterprise-grade JobFile entries for historical job runs. '
        'Uses realistic filesystem templates per client type; deterministic via MD5 seeding.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete all existing JobFile records before populating',
        )
        parser.add_argument(
            '--only-successful', action='store_true', default=True,
            help='Only generate file entries for T/W jobs (default: True)',
        )
        parser.add_argument(
            '--all-statuses', action='store_true',
            help='Generate file entries for all job statuses (overrides --only-successful)',
        )

    def handle(self, *args, **options):
        if options['clear']:
            deleted, _ = JobFile.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Cleared {deleted} existing JobFile record(s).'))

        only_ok = not options['all_statuses']

        qs = Job.objects.filter(name__in=_JOB_CLIENT.keys())
        if only_ok:
            qs = qs.filter(status__in=['T', 'W'])
        jobs = list(qs.order_by('actual_time'))

        self.stdout.write(f'Processing {len(jobs)} job(s)…')

        created_files  = 0
        updated_jobs   = 0
        fileset_updates = []

        with transaction.atomic():
            for job in jobs:
                client_name = _JOB_CLIENT.get(job.name)
                template    = _FS.get(client_name, [])
                if not template:
                    continue

                level    = job.level or 'F'
                job_start = job.actual_time

                entries = []
                for idx, (parent, name, is_dir, lo, hi, vol) in enumerate(template):
                    seed = f'fs{job.bareos_id}{idx}{name}'
                    if not _include(seed, vol, level):
                        continue
                    size    = 0 if is_dir else _seeded_size(f'sz{seed}', lo, hi)
                    mtime   = None if is_dir else _seeded_mtime(f'mt{seed}', job_start, level)
                    entries.append(JobFile(
                        job      = job,
                        path     = parent,
                        name     = name,
                        is_dir   = is_dir,
                        size     = size,
                        mod_time = mtime,
                    ))

                if not entries:
                    continue

                JobFile.objects.bulk_create(entries)
                created_files += len(entries)

                # Update job statistics
                file_entries = [e for e in entries if not e.is_dir]
                total_bytes  = sum(e.size for e in file_entries)
                total_files  = len(file_entries)

                fileset_updates.append(
                    Job(
                        pk          = job.pk,
                        files       = total_files,
                        bytes       = total_bytes,
                        filesets    = _JOB_FILESET.get(job.name, ''),
                    )
                )
                updated_jobs += 1

            # Bulk-update job stats
            if fileset_updates:
                Job.objects.bulk_update(fileset_updates, ['files', 'bytes', 'filesets'])

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Created {created_files} file entries across {updated_jobs} job(s).'
            )
        )
