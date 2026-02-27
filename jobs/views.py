# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

"""Views for jobs app."""
import json as _json

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from .models import Job, JobFile, JobLog


@login_required
def jobs_list(request):
    """List all jobs with filtering and pagination."""
    # Multi-value filters (checkboxes)
    status_filters = request.GET.getlist('status')
    level_filters  = request.GET.getlist('level')

    # Single-value filters
    client_filter = request.GET.get('client', '')
    search        = request.GET.get('search', '')
    date_from     = request.GET.get('date_from', '')
    date_to       = request.GET.get('date_to', '')
    zero_bytes    = request.GET.get('zero_bytes', '')

    queryset = Job.objects.select_related('client').all()

    if status_filters:
        queryset = queryset.filter(status__in=status_filters)
    if level_filters:
        queryset = queryset.filter(level__in=level_filters)
    if client_filter:
        queryset = queryset.filter(client__name__icontains=client_filter)
    if search:
        queryset = queryset.filter(name__icontains=search)
    if date_from:
        queryset = queryset.filter(actual_time__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(actual_time__date__lte=date_to)
    if zero_bytes:
        queryset = queryset.filter(bytes=0)

    # Pagination
    per_page  = int(request.GET.get('per_page', 25))
    page      = request.GET.get('page', 1)
    paginator = Paginator(queryset, per_page)
    jobs_page = paginator.get_page(page)

    total_jobs = queryset.count()
    successful = queryset.filter(status__in=['T', 'W']).count()
    failed     = queryset.filter(status__in=['F', 'E', 'A']).count()
    running    = queryset.filter(status='R').count()

    context = {
        'title': 'Jobs',
        'jobs': jobs_page,
        'total_jobs': total_jobs,
        'successful': successful,
        'failed': failed,
        'running': running,
        'status_filters': status_filters,
        'level_filters':  level_filters,
        'client_filter':  client_filter,
        'search':         search,
        'date_from':      date_from,
        'date_to':        date_to,
        'zero_bytes':     zero_bytes,
        'per_page':       per_page,
        'job_statuses': Job.STATUS_CHOICES,
        'job_levels':   Job.LEVEL_CHOICES,
    }
    return render(request, 'jobs/list.html', context)


@login_required
def job_detail(request, job_id):
    """Job detail dialog content (loaded into overlay-dialog via fetch)."""
    job  = get_object_or_404(Job.objects.select_related('client'), pk=job_id)
    logs = list(job.logs.order_by('timestamp')[:500])
    mode = request.GET.get('mode', '')

    file_entries = []
    trend_data   = []

    if mode == 'gantt':
        # Historical runs of same job name, oldest→newest (up to 30)
        history = list(
            Job.objects
            .filter(name=job.name, actual_time__isnull=False)
            .exclude(status='R')
            .order_by('-actual_time')[:30]
        )
        history.reverse()
        for h in history:
            if h.actual_time and h.end_time:
                dur_min = round((h.end_time - h.actual_time).total_seconds() / 60, 1)
            else:
                dur_min = 0.0
            trend_data.append({
                'date':    h.actual_time.strftime('%d.%m'),
                'dur_min': dur_min,
                'status':  h.status,
            })
    else:
        file_entries = list(job.file_entries.values('path', 'name', 'size', 'is_dir', 'mod_time'))
        for entry in file_entries:
            if entry['mod_time']:
                entry['mod_time'] = entry['mod_time'].strftime('%d.%m.%Y %H:%M')
            else:
                entry['mod_time'] = None

    context = {
        'job':        job,
        'logs':       logs,
        'job_files':  file_entries,
        'trend_data': trend_data,
        'mode':       mode,
    }
    return render(request, 'jobs/detail.html', context)


@login_required
@require_http_methods(['GET'])
def job_log(request, job_id):
    """Return job log messages as JSON (used by single-click log panel)."""
    job  = get_object_or_404(Job.objects.select_related('client'), pk=job_id)
    logs = list(
        job.logs.values('message', 'timestamp').order_by('-timestamp')[:100]
    )
    return JsonResponse({
        'job': {
            'id':       job.id,
            'bareos_id': job.bareos_id,
            'name':     job.name,
            'client':   job.client.name if job.client else '—',
            'status':   job.get_status_display(),
            'status_code': job.status,
            'level':    job.get_level_display_short(),
            'start':    job.actual_time.strftime('%d.%m.%Y %H:%M') if job.actual_time else '—',
            'end':      job.end_time.strftime('%d.%m.%Y %H:%M') if job.end_time else '—',
            'duration': job.duration_str,
            'files':    job.files,
            'bytes':    job.bytes,
            'errors':   job.errors,
            'pool':     job.pool_name,
            'storage':  job.storage_name,
            'fileset':  job.filesets,
        },
        'logs': [
            {
                'timestamp': e['timestamp'].strftime('%d.%m.%Y %H:%M:%S') if e['timestamp'] else '',
                'message':   e['message'],
            }
            for e in logs
        ],
    })


@login_required
@require_http_methods(['GET'])
def jobs_api(request):
    """API endpoint for jobs data (JSON for AJAX/WebSocket)."""
    page  = request.GET.get('page', 1)
    limit = int(request.GET.get('limit', 20))

    queryset = Job.objects.select_related('client').all()

    if status := request.GET.get('status'):
        queryset = queryset.filter(status=status)
    if client := request.GET.get('client'):
        queryset = queryset.filter(client__name__icontains=client)
    if level := request.GET.get('level'):
        queryset = queryset.filter(level=level)

    paginator = Paginator(queryset, limit)
    page_obj  = paginator.get_page(page)

    jobs_data = []
    for job in page_obj:
        jobs_data.append({
            'id':          job.id,
            'bareos_id':   job.bareos_id,
            'name':        job.name,
            'client':      job.client.name if job.client else 'N/A',
            'status':      job.get_status_display(),
            'status_code': job.status,
            'level':       job.get_level_display_short(),
            'actual_time': job.actual_time.isoformat() if job.actual_time else None,
            'end_time':    job.end_time.isoformat() if job.end_time else None,
            'duration':    job.duration_str,
            'bytes':       job.bytes,
            'files':       job.files,
            'errors':      job.errors,
        })

    return JsonResponse({
        'status':      'ok',
        'count':       page_obj.paginator.count,
        'page':        page,
        'total_pages': page_obj.paginator.num_pages,
        'jobs':        jobs_data,
    })
