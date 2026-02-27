"""Views for storage app."""
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404, render

from jobs.models import Job
from .models import Pool, Storage, Volume


# ── Helpers ───────────────────────────────────────────────────────────────────

def _volume_status_bar(volumes_qs):
    """Return list of {status, count, bytes, pct} dicts for a status bar."""
    STATUS_ORDER = ['Append', 'Full', 'Archive', 'Recycle', 'Purged', 'Error', 'Disabled', 'Cleaning']
    STATUS_COLOR = {
        'Append':   'var(--color-status-success)',
        'Full':     'var(--color-status-pending)',
        'Archive':  'var(--color-status-info)',
        'Recycle':  'var(--color-status-warning)',
        'Purged':   'var(--color-text-disabled)',
        'Error':    'var(--color-status-error)',
        'Disabled': 'var(--color-status-canceled)',
        'Cleaning': 'var(--color-status-running)',
    }
    agg = volumes_qs.values('status').annotate(count=Count('id'), total=Sum('bytes'))
    by_status = {row['status']: row for row in agg}
    total_count = sum(r['count'] for r in by_status.values()) or 1
    result = []
    for s in STATUS_ORDER:
        if s in by_status:
            row = by_status[s]
            result.append({
                'status': s,
                'count':  row['count'],
                'bytes':  row['total'] or 0,
                'pct':    round(row['count'] / total_count * 100, 1),
                'color':  STATUS_COLOR.get(s, '#888'),
            })
    return result


def _fmt_bytes(b):
    """Human-readable bytes."""
    if b is None:
        return '—'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB', 'PB'):
        if b < 1024:
            return f'{b:.1f} {unit}'
        b /= 1024
    return f'{b:.1f} PB'


# ── Main view ─────────────────────────────────────────────────────────────────

@login_required
def storage_view(request):
    storages = Storage.objects.annotate(
        pool_count=Count('pools', distinct=True),
        volume_count=Count('pools__volumes', distinct=True),
    ).order_by('name')

    first = storages.first()
    selected_storage = None
    pools            = []
    storage_stats    = None

    if first:
        selected_storage = first
        pools            = _get_pools(first)
        storage_stats    = _compute_storage_stats(first)

    return render(request, 'storage/list.html', {
        'storages':         storages,
        'selected_storage': selected_storage,
        'pools':            pools,
        'stats':            storage_stats,
        'app_name':         'storage',
    })


# ── HTMX partials ─────────────────────────────────────────────────────────────

@login_required
def storage_pools_htmx(request, pk):
    """Return pool list sidebar partial for a given storage."""
    storage = get_object_or_404(Storage, pk=pk)
    pools   = _get_pools(storage)
    return render(request, 'storage/partials/pools.html', {
        'storage': storage,
        'pools':   pools,
    })


@login_required
def storage_stats_htmx(request, pk):
    """Return stats panel partial for a storage."""
    storage = get_object_or_404(Storage, pk=pk)
    return render(request, 'storage/partials/storage_stats.html',
                  _compute_storage_stats(storage))


@login_required
def pool_stats_htmx(request, pk):
    """Return stats panel partial for a pool."""
    pool    = get_object_or_404(Pool, pk=pk)
    volumes = pool.volumes.order_by('-last_written')

    total_bytes  = volumes.aggregate(s=Sum('bytes'))['s'] or 0
    total_files  = volumes.aggregate(s=Sum('files'))['s'] or 0
    status_bar   = _volume_status_bar(volumes)

    return render(request, 'storage/partials/pool_stats.html', {
        'pool':        pool,
        'volumes':     volumes[:50],
        'total_bytes': _fmt_bytes(total_bytes),
        'total_files': total_files,
        'vol_count':   volumes.count(),
        'status_bar':  status_bar,
        'fmt_bytes':   _fmt_bytes,
    })


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_pools(storage):
    return storage.pools.annotate(
        vol_count=Count('volumes'),
        vol_bytes=Sum('volumes__bytes'),
    ).order_by('name')


def _compute_storage_stats(storage):
    volumes     = Volume.objects.filter(pool__storage=storage)
    total_bytes = volumes.aggregate(s=Sum('bytes'))['s'] or 0
    total_files = volumes.aggregate(s=Sum('files'))['s'] or 0
    vol_count   = volumes.count()
    pool_count  = storage.pools.count()
    status_bar  = _volume_status_bar(volumes)

    recent_jobs = (Job.objects
                   .filter(storage_name=storage.name)
                   .order_by('-actual_time')[:8])

    return {
        'storage':    storage,
        'pool_count': pool_count,
        'vol_count':  vol_count,
        'total_bytes': _fmt_bytes(total_bytes),
        'total_files': total_files,
        'status_bar':  status_bar,
        'recent_jobs': recent_jobs,
        'fmt_bytes':   _fmt_bytes,
    }
