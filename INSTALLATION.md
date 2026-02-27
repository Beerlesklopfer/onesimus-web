# Installation Guide - Onesimus Web Application

## Quick Start (Development)

### 1. Clone/Navigate to Project
```bash
cd /home/INTRANET.BERNAU.FAMILY/Joerg.Bernau/Nextcloud/Dokumente/Projekte/Qt/Onesimus
```

### 2. Create Virtual Environment
```bash
cd web
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
# Minimal installation (fastest)
pip install -r requirements-minimal.txt

# OR full installation (all dependencies)
pip install -r requirements.txt
```

### 4. Initialize Database
```bash
python manage.py migrate
python manage.py populate_mock_jobs
```

### 5. Create Admin User
```bash
python manage.py createsuperuser
# Username: admin
# Email: admin@example.local
# Password: admin
```

### 6. Run Development Server
```bash
daphne -b 0.0.0.0 -p 8000 onesimus.asgi:application
```

Or use the startup script:
```bash
cd ..
./run-web.sh
```

## Installation Options

### Option A: Minimal (Fastest)
Use `requirements-minimal.txt` - only direct dependencies
```bash
pip install -r requirements-minimal.txt
```
**Best for**: Quick testing, CI/CD pipelines
**Size**: ~500MB

### Option B: Full (Recommended for Development)
Use `requirements.txt` - all dependencies with versions pinned
```bash
pip install -r requirements.txt
```
**Best for**: Development, debugging
**Size**: ~800MB

### Option C: Development
Use `requirements-dev.txt` - includes testing, linting, debugging tools
```bash
pip install -r requirements-dev.txt
```
**Best for**: Active development, quality assurance
**Size**: ~1.2GB
**Includes**:
- pytest (testing)
- black (code formatting)
- ruff (linting)
- django-debug-toolbar (debugging)

### Option D: Production
Use `requirements-prod.txt` - optimized for deployment
```bash
pip install -r requirements-prod.txt
```
**Best for**: Deploying to production server
**Size**: ~700MB
**Includes**:
- psycopg2 (PostgreSQL support)
- gunicorn (WSGI server)
- redis (caching)

## Updating Requirements

### If you install new packages:
```bash
pip freeze > requirements.txt
```

### If dependencies change upstream:
```bash
pip install --upgrade -r requirements.txt
```

## Troubleshooting

### Port 8000 already in use
```bash
# Use a different port
daphne -b 0.0.0.0 -p 8001 onesimus.asgi:application

# Or kill existing process
pkill -f "daphne"
```

### Permission denied for venv
```bash
chmod +x .venv/bin/activate
source .venv/bin/activate
```

### Database locked
```bash
rm db.sqlite3
python manage.py migrate
python manage.py populate_mock_jobs
```

### Module not found errors
```bash
# Verify venv is activated
which python  # Should show .venv/bin/python

# Reinstall requirements
pip install -r requirements.txt
```

## Python Version Requirements

- **Minimum**: Python 3.11
- **Recommended**: Python 3.13+
- **Django 6.0.2** requires Python 3.10+

Check your version:
```bash
python --version
python3 --version
```

## Package Versions

### Core Framework
- Django 6.0.2
- Channels 4.3.2
- Daphne 4.2.1

### Backend Integration
- python-bareos 25.0.2

### Frontend
- django-htmx 1.27.0

### Environment
- python-dotenv 1.2.1

All versions are pinned to ensure consistency across environments.

## Platform Support

- **Linux**: ✅ Full support (tested on Debian/Ubuntu)
- **macOS**: ✅ Full support
- **Windows**: ✅ Full support (use WSL2 recommended)

## Next Steps

1. **Start development**:
   ```bash
   ./run-web.sh
   ```

2. **Access application**:
   - Web: http://localhost:8000
   - Admin: http://localhost:8000/admin
   - Credentials: admin / admin

3. **Test the Jobs module**:
   - Navigate to http://localhost:8000/jobs/
   - Filter jobs by status, level, client
   - Click "Detail" to see full job information

## Additional Resources

- [Django Documentation](https://docs.djangoproject.com/en/6.0/)
- [Channels Documentation](https://channels.readthedocs.io/)
- [Daphne ASGI Server](https://github.com/django/daphne)
- [HTMX Documentation](https://htmx.org/)
