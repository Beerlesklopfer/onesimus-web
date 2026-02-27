# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

"""Views for schedule app."""
import hashlib
import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .models import Schedule

_TOTAL_WEEK_MIN = 7 * 24 * 60  # 10 080


def _format_duration(minutes: int) -> str:
    """Format minutes as '4h' or '45m' or '2h 30m'."""
    if minutes <= 0:
        return '—'
    if minutes < 60:
        return f'{minutes}m'
    h, m = divmod(minutes, 60)
    return f'{h}h {m:02d}m' if m else f'{h}h'


def _bar_status(sched_name: str, day: int, h: int, m: int,
                week_offset: int, now_day: int, now_min_total: int) -> str:
    """Return a deterministic status code for a scheduled run slot.

    week_offset: 0 = current week, <0 = past, >0 = future
    now_day / now_min_total: today's weekday and minutes-since-Mon-00:00
    """
    if week_offset > 0:
        return 'q'  # future weeks: always scheduled

    bar_total = day * 1440 + h * 60 + m  # minutes since Mon 00:00

    if week_offset == 0:
        delta = now_min_total - bar_total  # positive = past
        if delta < -5:
            return 'q'   # not yet started
        if delta < 90:
            return 'R'   # currently running (≈ ±90 min window)
        # fall through to past-run logic

    # Past run: deterministic status derived from a hash of the slot
    digest = hashlib.md5(f'{sched_name}{day}{h}{m}{week_offset}'.encode()).hexdigest()[:8]
    seed = int(digest, 16)
    opts = ['T', 'T', 'T', 'T', 'W', 'W', 'F']
    return opts[seed % len(opts)]


def _overall_status(run_entries: list) -> str:
    """Derive the worst status from a list of run entries for the sidebar dot."""
    priority = {'F': 0, 'E': 1, 'A': 2, 'W': 3, 'R': 4, 'T': 5, 'q': 6}
    past = [r['status'] for r in run_entries if r['status'] not in ('q',)]
    if not past:
        return 'q'
    return min(past, key=lambda s: priority.get(s, 99))


@login_required
def gantt_view(request):
    """Display Gantt timeline view of job schedules."""
    week_offset = int(request.GET.get('week', 0))

    # Current week Mon–Sun based on today + offset
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    monday += timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)

    week_label = (
        f'{monday.strftime("%a %-d %b")} – {sunday.strftime("%a %-d %b %Y")}'
    )
    week_dates = [monday + timedelta(days=d) for d in range(7)]

    # Highlight today only when viewing the current week
    today_weekday = today.weekday() if week_offset == 0 else -1

    # "Now" position as % of total week width (None for non-current weeks)
    now = timezone.localtime()
    now_day = today.weekday()
    now_min_total = now_day * 1440 + now.hour * 60 + now.minute
    if week_offset == 0:
        now_pct = round(now_min_total / _TOTAL_WEEK_MIN * 100, 4)
        # CSS calc offset: 150px (label width) × (1 - now_pct/100)
        now_line_offset_px = round(150 * (1 - now_pct / 100), 2)
    else:
        now_pct = None
        now_line_offset_px = None

    # Build Gantt data
    schedules_qs = (
        Schedule.objects
        .select_related('job', 'job__client')
        .filter(enabled=True)
        .order_by('name')
    )

    gantt_schedules = []
    total_runs = 0

    for sched in schedules_qs:
        job = sched.job
        run_entries = []
        max_dur = 0

        for rt in (sched.run_times or []):
            days    = rt.get('days', [])
            at_str  = rt.get('at', '00:00')
            dur_min = int(rt.get('duration_min', 30))
            level   = rt.get('level', 'F')
            max_dur = max(max_dur, dur_min)

            h, m = map(int, at_str.split(':'))

            for day in days:
                start_min = day * 1440 + h * 60 + m
                status = _bar_status(
                    sched.name, day, h, m,
                    week_offset, now_day, now_min_total,
                )
                run_entries.append({
                    'day':       day,
                    'at':        at_str,
                    'level':     level,
                    'dur_min':   dur_min,
                    'status':    status,
                    'pct_start': round(start_min / _TOTAL_WEEK_MIN * 100, 4),
                    'pct_width': max(0.3, round(dur_min / _TOTAL_WEEK_MIN * 100, 4)),
                })
                total_runs += 1

        gantt_schedules.append({
            'id':             sched.id,
            'name':           sched.name,
            'job_id':         job.id          if job              else None,
            'job_name':       job.name        if job              else '—',
            'client_name':    job.client.name if (job and job.client) else '—',
            'storage':        job.storage_name if job             else '—',
            'pool':           job.pool_name    if job             else '—',
            'est_dur':        _format_duration(max_dur),
            'overall_status': _overall_status(run_entries),
            'runs':           run_entries,
        })

    context = {
        'title':               'Schedules',
        'week_offset':         week_offset,
        'week_label':          week_label,
        'week_dates':          week_dates,
        'today_weekday':       today_weekday,
        'now_pct':             now_pct,
        'now_line_offset_px':  now_line_offset_px,
        'gantt_schedules':     gantt_schedules,
        'schedule_count':      len(gantt_schedules),
        'total_runs':          total_runs,
    }
    return render(request, 'schedule/gantt.html', context)


@login_required
def weekly_view(request):
    """Display weekly planner grid view of job schedules."""
    context = {
        'title': 'Schedules - Weekly Plan',
    }
    return render(request, 'schedule/weekly.html', context)
