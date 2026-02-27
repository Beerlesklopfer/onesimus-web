"""Management command to populate mock Storage, Pool and Volume records."""
import hashlib
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from storage.models import Storage, Pool, Volume

# ── Helpers ───────────────────────────────────────────────────────────────────

def _md5int(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

def _sz(seed: str, lo: int, hi: int) -> int:
    return lo + _md5int(seed) % (hi - lo + 1)

def _dt(seed: str, base, max_days: int):
    delta = timedelta(seconds=_md5int(seed) % (max_days * 86_400))
    return base - delta


# ── Mock data ─────────────────────────────────────────────────────────────────

_STORAGES = [
    # (bareos_id, name, address, port, storage_type, status)
    (1, 'File-SD', '192.168.1.14', 9103, 'File', 'online'),
    (2, 'Tape-SD', '192.168.1.14', 9103, 'Tape', 'online'),
]

_POOLS = [
    # (bareos_id, name, storage_name, pool_type, max_volumes, recycle_oldest, recycle_current)
    (1, 'Full',         'File-SD', 'Backup', 0,  False, False),
    (2, 'Incremental',  'File-SD', 'Backup', 0,  True,  False),
    (3, 'Differential', 'File-SD', 'Backup', 0,  False, False),
    (4, 'Home',         'File-SD', 'Backup', 10, False, True),
    (5, 'Tape-Full',    'Tape-SD', 'Backup', 50, False, False),
    (6, 'Tape-Archive', 'Tape-SD', 'Archive',100, False, False),
]

# Volume templates: (pool_name, vol_prefix, count, status_weights, size_lo_gb, size_hi_gb)
_VOLUMES = [
    ('Full',         'Vol-Full',    12, [('Full',6),('Append',2),('Purged',3),('Recycle',1)],          50,  800),
    ('Incremental',  'Vol-Inc',     30, [('Append',12),('Full',10),('Purged',6),('Recycle',2)],         1,   20),
    ('Differential', 'Vol-Diff',    10, [('Full',5),('Append',2),('Purged',2),('Recycle',1)],          10,  100),
    ('Home',         'Vol-Home',     6, [('Append',2),('Full',3),('Purged',1)],                        20,  200),
    ('Tape-Full',    'T',           20, [('Full',10),('Append',3),('Archive',4),('Purged',2),('Error',1)], 200, 2000),
    ('Tape-Archive', 'A',           15, [('Archive',10),('Full',4),('Purged',1)],                     200, 2000),
]


def _pick_status(seed: str, weights) -> str:
    """Deterministic weighted status pick."""
    total = sum(w for _, w in weights)
    r = _md5int(seed) % total
    cumulative = 0
    for status, w in weights:
        cumulative += w
        if r < cumulative:
            return status
    return weights[0][0]


class Command(BaseCommand):
    help = 'Populate database with mock Storage, Pool and Volume records'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true',
                            help='Delete existing records before populating')

    def handle(self, *args, **options):
        now = timezone.now()

        if options['clear']:
            Volume.objects.all().delete()
            Pool.objects.all().delete()
            Storage.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared existing storage records.'))

        # ── Storages ──────────────────────────────────────────────────────────
        storage_map = {}
        for bid, name, address, port, stype, status in _STORAGES:
            obj, created = Storage.objects.update_or_create(
                bareos_id=bid,
                defaults=dict(name=name, address=address, port=port,
                              storage_type=stype, status=status),
            )
            storage_map[name] = obj
            self.stdout.write(f'  {"+" if created else "~"} Storage: {name}')

        # ── Pools ─────────────────────────────────────────────────────────────
        pool_map = {}
        for bid, name, storage_name, ptype, maxvol, rec_old, rec_cur in _POOLS:
            storage = storage_map.get(storage_name)
            obj, created = Pool.objects.update_or_create(
                bareos_id=bid,
                defaults=dict(name=name, storage=storage, pool_type=ptype,
                              max_volumes=maxvol, recycle_oldest_volume=rec_old,
                              recycle_current_volume=rec_cur),
            )
            pool_map[name] = obj
            self.stdout.write(f'  {"+" if created else "~"} Pool: {name} → {storage_name}')

        # ── Volumes ───────────────────────────────────────────────────────────
        vol_created = vol_updated = 0
        bareos_id = 1000

        for pool_name, prefix, count, status_weights, size_lo_gb, size_hi_gb in _VOLUMES:
            pool = pool_map.get(pool_name)
            if not pool:
                continue

            for i in range(1, count + 1):
                vol_name = f'{prefix}-{i:04d}'
                seed     = f'{pool_name}-{vol_name}'

                status      = _pick_status(seed + '-status', status_weights)
                size_bytes  = _sz(seed + '-sz', size_lo_gb * 1024**3, size_hi_gb * 1024**3)
                file_count  = _sz(seed + '-fc', 100, 500_000)
                last_w      = _dt(seed + '-lw', now, 90)
                first_w     = last_w - timedelta(days=_sz(seed + '-fw', 1, 60))

                # Purged/Recycle volumes have no meaningful bytes left
                if status in ('Purged', 'Recycle'):
                    size_bytes = _sz(seed + '-pz', 0, 1024**3)

                obj, created = Volume.objects.update_or_create(
                    name=vol_name,
                    defaults=dict(
                        bareos_id=bareos_id,
                        pool=pool,
                        status=status,
                        bytes=size_bytes,
                        files=file_count,
                        first_written=first_w,
                        last_written=last_w,
                    ),
                )
                if created:
                    vol_created += 1
                else:
                    vol_updated += 1
                bareos_id += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done. Volumes: {vol_created} created, {vol_updated} updated.'
        ))
