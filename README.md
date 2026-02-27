# Onesimus Web Application - Phase 3 MVP

## Overview

This is the web-based frontend for Onesiums backup management system, built with Django, HTMX, and WebSockets.

**Current Version**: Phase 3 MVP - Jobs Management
**Status**: Development/Testing

## Features Implemented

### Phase 1 ✅ (Foundation)
- Django 6.0.2 project with 5 apps (common, jon, clients, schedule, storage)
- Daphne + Django Channels for WebSocket support
- Base HTML templates (navbar, sidebar, footer)
- CSS system with dark/light theme support
- HTMX integration for dynamic updates
- Bareos Director connection wrapper

### Phase 2 ✅ (UI Components)
- CSS variables for theming (50+ colors, spacing, typography)
- Reusable components (buttons, badges, cards, forms, tables, modals)
- Responsive grid layout (mobile-first)
- Theme toggle (dark/light) with localStorage

### Phase 3 ✅ (Jobs MVP - NOW)
- Job models with all Bareos fields (status, level, bytes, files, errors)
- Jobs list view with pagination (20 jobs/page)
- Filtering by status, client, level, name
- Job detail page with full information
- Mock data (50 sample jobs, 5 mock clients)
- Job statistics (successful, running, failed counts)
- Job logs display
- Status badges with color coding
- Admin interface for Job management

## Quick Start

### 1. Start the Development Server

```bash
cd /home/INTRANET.BERNAU.FAMILY/Joerg.Bernau/Nextcloud/Dokumente/Projekte/Qt/Onesimus
./run-web.sh
```

The server will:
- Activate the Python venv
- Run migrations
- Create admin user `admin` / `admin` (if not exists)
- Collect static files
- Start Daphne on `http://localhost:8000`

### 2. Access the Application

**Web Interface**: http://localhost:8000
**Admin Panel**: http://localhost:8000/admin
**Login**:
- Username: `admin`
- Password: `admin`

### 3. Test the Jobs Module

- Navigate to **Jobs** tab in sidebar
- You'll see 50 mock jobs with various statuses (Completed, Running, Failed)
- Try filtering by:
  - **Status**: Completed, Running, Failed, etc.
  - **Level**: Full, Incremental, Differential
  - **Client**: Search for any client name
  - **Search**: Find jobs by name
- Click any job's **Detail** button to see full job information
- Pagination: Navigate through pages with First/Prev/Next/Last buttons

## Project Structure

```
web/
├── .venv/                          # Python virtual environment
├── manage.py                       # Django management script
├── db.sqlite3                      # Development database (populated with mock data)
├── staticfiles/                    # Collected static files
├── onesimus/                       # Django project config
│   ├── settings.py                 # Installed apps, middleware, static files
│   ├── asgi.py                     # WebSocket routing (Daphne)
│   └── urls.py                     # URL routing
├── common/                         # Shared functionality
│   ├── templates/common/           # Base layouts (navbar, sidebar, footer)
│   ├── static/common/
│   │   ├── css/                    # (variables, base, components, layout)
│   │   └── js/                     # (htmx, ws-manager, common.js)
│   ├── directorconnection.py       # Bareos JSON-RPC wrapper
│   └── consumers.py                # Base WebSocket consumer
├── jon/                            # Jobs app (Phase 3 MVP)
│   ├── models.py                   # Job, JobFile, JobLog models
│   ├── views.py                    # List, detail, API endpoints
│   ├── consumers.py                # WebSocket for job updates
│   ├── admin.py                    # Django admin interface
│   ├── urls.py                     # Job URLs
│   ├── templates/jon/
│   │   ├── list.html               # Jobs table (with filters + pagination)
│   │   └── detail.html             # Job detail page
│   └── management/commands/
│       └── populate_mock_jobs.py   # Command to generate 50 mock jobs
├── clients/                        # Clients app (Phase 4)
├── schedule/                       # Schedules app (Phase 5)
└── storage/                        # Storage app (Future)
```

## Database Schema

### Job Model
- `bareos_id` (unique)
- `name`, `client` (ForeignKey to Client)
- `level` (F/I/D/V - Full/Incremental/Differential/VirtualFull)
- `status` (T/W/F/E/R/A - Completed/Warning/Failed/Error/Running/Aborted)
- `actual_time`, `end_time` (when job ran)
- `bytes`, `files`, `errors` (statistics)
- Indexes on: bareos_id, status+actual_time, client+actual_time, level+actual_time

### Client Model
- `bareos_id` (unique)
- `name` (unique)
- `status` (online/offline/disabled/connecting)
- `address`, `port` (connection info)
- `version`, `uname` (client info)
- `last_backup`, `total_bytes` (statistics)

### JobFile & JobLog Models
- `JobFile`: For BVFS file listings (job → files relation)
- `JobLog`: Job log messages with timestamps

## Populate Mock Data

If you need to repopulate the mock jobs:

```bash
cd web
source .venv/bin/activate
python manage.py populate_mock_jobs
```

This creates:
- 5 mock clients (web-server, db-server, file-server, backup-server, mail-server)
- 50 mock jobs with random status, level, timing, and statistics

## Environment Setup

### Python Version
- Python 3.13+ (required for Django 6.0.2)

### Dependencies
- Django 6.0.2
- channels 4.0.0 (WebSocket support)
- daphne 4.0.0 (ASGI server)
- django-htmx 1.27.0
- python-bareos (for future Director integration)
- python-dotenv

### Development Settings
- Database: SQLite3 (for development, switch to PostgreSQL for production)
- Debug: True (development)
- SECRET_KEY: Hardcoded (⚠️ change for production)

## Next Steps

### Phase 4: Clients Module
- [ ] Create client list view with status filtering
- [ ] Real-time status updates via WebSocket
- [ ] Client detail modal with info, settings, job history, statistics

### Phase 5: Schedules Module
- [ ] Gantt timeline visualization (when jobs run)
- [ ] Weekly planner grid (7x24 hours)
- [ ] Drag-to-reschedule interaction
- [ ] Schedule creation wizard

### Phase 6: Restore Wizard
- [ ] Multi-step BVFS browser for file restoration
- [ ] Checkbox selection with tri-state for directories
- [ ] Restore options form
- [ ] Preview and confirmation

### Phase 7: Bareos Integration
- [ ] Connect DirectorConnection to real Bareos Director
- [ ] Implement sync service to load jobs from Director
- [ ] Real-time job status push via WebSocket
- [ ] Job control (run, cancel, restore)

## Testing Checklist

- [x] Log in with Django user (admin/admin)
- [x] Jobs list loads with mock data
- [x] Pagination works (20 jobs/page)
- [x] Filtering works (status, level, client, search)
- [x] Job detail page shows all information
- [x] Status badges display correctly with colors
- [x] Theme toggle switches dark/light
- [ ] WebSocket connection (real-time updates) - Phase 7
- [ ] Client list and status - Phase 4
- [ ] Schedules Gantt and Weekly views - Phase 5

## Admin Interface

Access Django admin at `/admin`:

**Job Management**:
- View/edit all jobs
- Filter by status, level, date range
- Search by name or client

**Client Management** (Phase 4):
- Manage clients and their status

**Advanced**:
- User management
- Groups and permissions
- Database cleanup

## Configuration

### settings.py Key Settings

```python
DEBUG = True                          # Set to False for production
SECRET_KEY = '...'                   # Change for production!
ALLOWED_HOSTS = []                   # Add hostnames for production
DATABASES = {...}                    # Switch to PostgreSQL for production

INSTALLED_APPS = [
    'daphne',                        # WebSocket support
    'channels',                      # Django Channels
    'common',                        # Shared app
    'jon', 'clients', 'schedule', 'storage',
]

ASGI_APPLICATION = 'onesimus.asgi.application'  # Daphne
CHANNEL_LAYERS = {'default': {...}}             # WebSocket config
```

### asgi.py WebSocket Routes

```python
websocket_urlpatterns = [
    path('ws/notifications/', NotificationConsumer.as_asgi()),
    path('ws/jobs/updates/', JobsConsumer.as_asgi()),
    path('ws/clients/updates/', ClientsConsumer.as_asgi()),
    path('ws/schedules/updates/', SchedulesConsumer.as_asgi()),
]
```

## Troubleshooting

**"Module not found" errors**:
```bash
cd web
source .venv/bin/activate
pip install -r ../requirements.txt  # Once we create one
```

**Database locked**:
```bash
rm db.sqlite3
python manage.py migrate
python manage.py populate_mock_jobs
```

**Port 8000 already in use**:
```bash
daphne -b 0.0.0.0 -p 8001 onesimus.asgi:application
```

**WebSocket not connecting**:
- Check browser console for errors
- Verify Daphne started (should say "HTTP/2 support enabled")
- Check firewall/proxy settings

## Performance Notes

For development:
- SQLite is fine (single-user)
- Daphne development server is adequate

For production:
- **Database**: Use PostgreSQL with proper indexes
- **Server**: Use Daphne + Gunicorn/uWSGI proxy
- **Static Files**: Serve via Nginx/CloudFront
- **WebSockets**: May need Redis for multi-process scaling
- **Cache**: Implement Redis for session/data caching

## Code Quality

Current state:
- ✅ Models: Well-structured with proper fields and indexes
- ✅ Views: Use Django best practices (queryset optimization, pagination)
- ✅ Templates: Semantic HTML, accessibility-friendly
- ✅ CSS: DRY with variables, no duplicate codes
- ✅ JavaScript: Vanilla JS only (HTMX + custom)

Future improvements:
- [ ] Unit tests (TestCase coverage > 80%)
- [ ] Integration tests for WebSocket
- [ ] Type hints (Python typing)
- [ ] Pre-commit hooks (black, ruff, mypy)
- [ ] API documentation (drf-spectacular or Swagger)

## License

MIT License — © 2025–2026 Jörg Bernau

## Support

For issues or questions:
- Check the [Qt Onesimus README](../README.md)
- Refer to the [Implementation Plan](../.claude/plans/*.md)
- Check Django/Channels documentation
