"""Common views: settings API, preferences API, and about dialog."""
import django
import json
import subprocess
import sys
from pathlib import Path

from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .models import Setting, UserPreference

_BUILD_NUMBER_FILE = Path(__file__).resolve().parent.parent.parent / '.build_number'


def _git_info():
    """Return (short_hash, branch) from git, or ('', '') on failure."""
    try:
        h = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'], stderr=subprocess.DEVNULL, text=True
        ).strip()
        b = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], stderr=subprocess.DEVNULL, text=True
        ).strip()
        return h, b
    except Exception:
        return '', ''


# ── Logout (GET + POST) ───────────────────────────────────────────────────

@require_http_methods(['GET', 'POST'])
def logout_view(request):
    """Accept both GET and POST logout so bookmarks / direct URL calls work."""
    auth_logout(request)
    return redirect('/accounts/login/')


# ── Profile dialog ────────────────────────────────────────────────────────

_ACL_RESOURCES = [
    # (resource_label, {role_key: access_label})
    ('Jobs',           {'superadmin': 'Full Control', 'admin': 'Run / Cancel / Restore', 'operator': 'Read Only'}),
    ('Clients',        {'superadmin': 'Full Control', 'admin': 'Enable / Disable',       'operator': 'Read Only'}),
    ('Storage',        {'superadmin': 'Full Control', 'admin': 'Read Only',               'operator': 'No Access'}),
    ('Schedules',      {'superadmin': 'Full Control', 'admin': 'Read / Edit',             'operator': 'Read Only'}),
    ('File Sets',      {'superadmin': 'Full Control', 'admin': 'Read Only',               'operator': 'Read Only'}),
    ('Pools',          {'superadmin': 'Full Control', 'admin': 'Read Only',               'operator': 'No Access'}),
    ('Volumes',        {'superadmin': 'Full Control', 'admin': 'Read Only',               'operator': 'No Access'}),
    ('Reports',        {'superadmin': 'Full Control', 'admin': 'Full Access',             'operator': 'Read Only'}),
    ('Administration', {'superadmin': 'Full Control', 'admin': 'Limited',                 'operator': 'No Access'}),
]


@login_required
@require_http_methods(['GET'])
def profile_view(request):
    user = request.user
    if user.is_superuser:
        role_key   = 'superadmin'
        role_label = 'Superadmin'
    elif user.is_staff:
        role_key   = 'admin'
        role_label = 'Administrator'
    else:
        role_key   = 'operator'
        role_label = 'Operator'

    acls = [
        {'resource': res, 'access': levels[role_key]}
        for res, levels in _ACL_RESOURCES
    ]
    return render(request, 'common/profile_dialog.html', {
        'profile_user': user,
        'role_label':   role_label,
        'role_key':     role_key,
        'acls':         acls,
    })


# ── About dialog ──────────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET'])
def about_view(request):
    build = _BUILD_NUMBER_FILE.read_text().strip() if _BUILD_NUMBER_FILE.exists() else '?'
    git_hash, git_branch = _git_info()
    return render(request, 'common/about_dialog.html', {
        'version': '0.2.0',
        'build': build,
        'git_hash': git_hash,
        'git_branch': git_branch,
        'django_version': django.get_version(),
        'python_version': f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}',
    })


# ── Global Settings (read-only for frontend) ──────────────────────────────

@login_required
@require_http_methods(['GET'])
def settings_api(request):
    """
    GET /common/settings/          → all global settings as {key: value}
    GET /common/settings/?key=foo  → single setting value
    """
    key = request.GET.get('key')
    if key:
        return JsonResponse({'key': key, 'value': Setting.get(key)})
    return JsonResponse(Setting.get_all())


# ── User Preferences ──────────────────────────────────────────────────────

@login_required
@require_http_methods(['GET', 'POST'])
def preferences_api(request):
    """
    GET  /common/preferences/?scope=jobs.filter
         → {key: value, ...} for the scope

    POST /common/preferences/
         body: {"scope": "jobs.filter", "key": "per_page", "value": 50}
         → {"ok": true}

    POST /common/preferences/ (bulk)
         body: {"scope": "jobs.filter", "data": {"per_page": 50, "status_open": true}}
         → {"ok": true, "saved": 2}
    """
    if request.method == 'GET':
        scope = request.GET.get('scope', '')
        return JsonResponse(UserPreference.get_scope(request.user, scope))

    # POST
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    scope = body.get('scope', '')
    if not scope:
        return JsonResponse({'error': 'scope required'}, status=400)

    # Bulk mode
    if 'data' in body:
        data = body['data']
        if not isinstance(data, dict):
            return JsonResponse({'error': 'data must be an object'}, status=400)
        UserPreference.set_many(request.user, scope, data)
        return JsonResponse({'ok': True, 'saved': len(data)})

    # Single key/value mode
    key = body.get('key')
    if not key:
        return JsonResponse({'error': 'key required'}, status=400)
    UserPreference.set(request.user, scope, key, body.get('value'))
    return JsonResponse({'ok': True})
