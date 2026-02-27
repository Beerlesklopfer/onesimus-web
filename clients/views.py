# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

"""Views for clients app."""
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Max, Sum, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Client


@login_required
def clients_list(request):
    """List all clients with filtering, sorting and statistics."""
    name_filter   = request.GET.get('name', '').strip()
    status_filter = request.GET.get('status', '').strip().lower()
    sort_col      = request.GET.get('sort', 'name')
    sort_dir      = request.GET.get('dir', 'asc')

    qs = Client.objects.annotate(
        job_count=Count('jobs', distinct=True),
        total_backed=Sum('jobs__bytes'),
    )

    if name_filter:
        qs = qs.filter(name__icontains=name_filter)
    if status_filter and status_filter != 'all':
        qs = qs.filter(status=status_filter)

    _sort_map = {
        'name':            'name',
        'address':         'address',
        'port':            'port',
        'status':          'status',
        'version':         'version',
        'last_connection': 'last_backup',
        'jobs':            'job_count',
        'total_data':      'total_backed',
    }
    db_col = _sort_map.get(sort_col, 'name')
    order  = db_col if sort_dir == 'asc' else f'-{db_col}'
    qs     = qs.order_by(order)

    clients = list(qs)

    total         = Client.objects.count()
    online_count  = Client.objects.filter(status='online').count()
    offline_count = Client.objects.filter(status__in=('offline', 'disabled')).count()
    unknown_count = Client.objects.filter(status__in=('unknown', 'connecting')).count()

    context = {
        'app_name':      'clients',
        'clients':       clients,
        'total':         total,
        'online_count':  online_count,
        'offline_count': offline_count,
        'unknown_count': unknown_count,
        'name_filter':   name_filter,
        'status_filter': status_filter,
        'sort_col':      sort_col,
        'sort_dir':      sort_dir,
        'status_choices': Client.STATUS_CHOICES,
    }
    return render(request, 'clients/list.html', context)


@login_required
def client_detail(request, client_id):
    """Client detail dialog content (loaded into overlay-dialog via fetch)."""
    client = get_object_or_404(
        Client.objects.annotate(
            job_count=Count('jobs', distinct=True),
            total_backed=Sum('jobs__bytes'),
            successful_count=Count('jobs', filter=Q(jobs__status__in=['T', 'W'])),
            failed_count=Count('jobs', filter=Q(jobs__status__in=['F', 'E', 'A'])),
        ),
        pk=client_id,
    )
    recent_jobs = client.jobs.order_by('-actual_time')[:15]

    days_offline = None
    if client.last_backup:
        days_offline = (timezone.now() - client.last_backup).days

    job_stats = client.jobs.aggregate(
        avg_bytes=Avg('bytes'),
        max_bytes=Max('bytes'),
        total_bytes=Sum('bytes'),
        total_files=Sum('files'),
    )

    # Generate bareos-style config preview
    import hashlib
    pw_hash = hashlib.md5(f'bareos-{client.bareos_id}-{client.name}'.encode()).hexdigest()
    config_pairs = [
        ('address',         client.address or '—'),
        ('autoprune',       'yes' if client.auto_prune else 'no'),
        ('catalog',         'MyCatalog'),
        ('fd port',         str(client.port)),
        ('file retention',  f'{client.file_retention_days} days'),
        ('job retention',   f'{client.job_retention_days} days'),
        ('password',        f'[md5]{pw_hash}'),
        ('tls cipher list', 'PSK-AES256-GCM-SHA384:PSK-CHACHA20-POLY1305'),
        ('tls enable',      'yes'),
        ('tls require',     'no'),
    ]
    conf_filename = f'{client.name}.conf'

    context = {
        'client':        client,
        'recent_jobs':   recent_jobs,
        'days_offline':  days_offline,
        'job_stats':     job_stats,
        'config_pairs':  config_pairs,
        'conf_filename': conf_filename,
    }
    return render(request, 'clients/detail.html', context)
