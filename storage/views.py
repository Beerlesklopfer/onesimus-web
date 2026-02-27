# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

"""Views for storage app."""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from jobs.models import Job
from .models import Pool, Storage, Volume

# Fixed palette — same indices used across storage and pool charts
_TREND_COLORS = [
    '#6af06a',  # green   (Full / pool 0)
    '#6ad4f0',  # cyan    (Incremental / pool 1)
    '#ffd06a',  # yellow  (Differential / pool 2)
    '#aa6af0',  # purple  (Virtual Full / pool 3)
    '#f06a6a',  # red     (pool 4)
    '#6a8af0',  # blue    (pool 5)
    '#f0a06a',  # orange  (pool 6)
]

_LEVEL_LABEL = {'F': 'Full', 'I': 'Incr', 'D': 'Diff', 'V': 'VFull', 'B': 'Base'}
_LEVEL_COLOR  = {'F': '#6af06a', 'I': '#6ad4f0', 'D': '#ffd06a', 'V': '#aa6af0', 'B': '#f0a06a'}

TREND_DAYS = 30


def _trend_by_group(jobs_qs, group_field, label_map=None, color_map=None, days=TREND_DAYS):
    """
    Aggregate successful job bytes by day and a group field.
    Returns (dates_list, series_list) where each series is
    {'name': str, 'values': [int…], 'color': str}.
    """
    from_dt = timezone.now() - timedelta(days=days)
    rows = (
        jobs_qs
        .filter(actual_time__gte=from_dt, status__in=('T', 'W'))
        .annotate(day=TruncDate('actual_time'))
        .values('day', group_field)
        .annotate(total=Sum('bytes'))
        .order_by('day', group_field)
    )
    all_days   = [(from_dt + timedelta(days=i)).date() for i in range(days + 1)]
    group_keys = sorted(set(r[group_field] for r in rows))
    if not group_keys:
        return all_days, []

    by_group = {g: {} for g in group_keys}
    for r in rows:
        by_group[r[group_field]][r['day']] = r['total']

    series = []
    for i, key in enumerate(group_keys):
        values = [by_group[key].get(d, 0) for d in all_days]
        if not any(values):
            continue
        label = (label_map or {}).get(key, key)
        color = (color_map or {}).get(key, _TREND_COLORS[i % len(_TREND_COLORS)])
        series.append({'name': label, 'values': values, 'color': color})
    return all_days, series


def _svg_trend(days_list, series, height=70):
    """Build an inline SVG area+line chart. Returns empty string if no data."""
    if not series:
        return ''
    max_val = max(v for s in series for v in s['values'])
    if max_val == 0:
        return ''

    W, H, PAD = 400, height, 2
    n = len(days_list)

    def px(i): return round(i / (n - 1) * W, 1)
    def py(v): return round(H - PAD - v / max_val * (H - PAD * 2), 1)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
             f'width="100%" height="{H}" preserveAspectRatio="none">']

    for s in series:
        pts  = ' '.join(f'{px(i)},{py(v)}' for i, v in enumerate(s['values']))
        area = f'0,{H} {pts} {W},{H}'
        c    = s['color']
        parts.append(f'<polygon points="{area}" fill="{c}" fill-opacity="0.15"/>')
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{c}" '
                     f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>')

    parts.append('</svg>')
    return ''.join(parts)


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

    # Trend: bytes per day, grouped by backup level
    jobs_qs = Job.objects.filter(pool_name=pool.name)
    trend_days, trend_series = _trend_by_group(
        jobs_qs, 'level', label_map=_LEVEL_LABEL, color_map=_LEVEL_COLOR,
    )
    trend_svg     = _svg_trend(trend_days, trend_series)
    trend_max_fmt = _fmt_bytes(max((v for s in trend_series for v in s['values']), default=0))

    return render(request, 'storage/partials/pool_stats.html', {
        'pool':           pool,
        'volumes':        volumes[:50],
        'total_bytes':    _fmt_bytes(total_bytes),
        'total_files':    total_files,
        'vol_count':      volumes.count(),
        'status_bar':     status_bar,
        'fmt_bytes':      _fmt_bytes,
        'trend_svg':      trend_svg,
        'trend_series':   trend_series,
        'trend_days':     trend_days,
        'trend_max_fmt':  trend_max_fmt,
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

    # Trend: bytes per day, grouped by pool name
    jobs_qs = Job.objects.filter(storage_name=storage.name)
    trend_days, trend_series = _trend_by_group(jobs_qs, 'pool_name')
    trend_svg     = _svg_trend(trend_days, trend_series)
    trend_max_fmt = _fmt_bytes(max((v for s in trend_series for v in s['values']), default=0))

    return {
        'storage':       storage,
        'pool_count':    pool_count,
        'vol_count':     vol_count,
        'total_bytes':   _fmt_bytes(total_bytes),
        'total_files':   total_files,
        'status_bar':    status_bar,
        'recent_jobs':   recent_jobs,
        'fmt_bytes':     _fmt_bytes,
        'trend_svg':     trend_svg,
        'trend_series':  trend_series,
        'trend_days':    trend_days,
        'trend_max_fmt': trend_max_fmt,
    }
