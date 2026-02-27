#!/usr/bin/env fish
# Start Onesimus Web Application

set SCRIPT_DIR (dirname (readlink -f (status filename)))
set WEB_DIR $SCRIPT_DIR

# --- Default values ---
set env_mode dev

# --- Usage ---
function usage
    echo "Usage: run-web.fish [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --dev    Development mode (default): DEBUG=true, requirements-dev.txt"
    echo "  --prod   Production mode: DEBUG=false, requirements-prod.txt"
    echo "  -h, --help  Show this help"
end

# --- Parse arguments ---
for arg in $argv
    switch $arg
        case --dev
            set env_mode dev
        case --prod
            set env_mode prod
        case -h --help
            usage
            exit 0
        case '*'
            echo "Unknown option: $arg"
            usage
            exit 1
    end
end

# --- Map mode to settings ---
if test $env_mode = prod
    set req_file requirements-prod.txt
    set -x DJANGO_DEBUG false
else
    set req_file requirements-dev.txt
    set -x DJANGO_DEBUG true
end

echo "🚀 Starting Onesimus Web Application ($env_mode mode)..."
echo "📁 Working directory: $WEB_DIR"
cd "$WEB_DIR"

# Activate venv
if not test -d .venv
    echo "❌ Virtual environment not found. Creating..."
    python3 -m venv .venv
    .venv/bin/pip install -U pip setuptools wheel
end

echo "📦 Installing dependencies ($req_file)..."
.venv/bin/pip install -q -r $req_file

source .venv/bin/activate.fish

# Run migrations if needed
echo "🔄 Running migrations..."
python manage.py migrate --noinput

# Create superuser if needed
if not python manage.py shell -c "from django.contrib.auth.models import User; exit(0 if User.objects.filter(username='admin').exists() else 1)" 2>/dev/null
    echo "👤 Creating superuser 'admin' with password 'admin'..."
    echo "from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@example.local', 'admin')" | python manage.py shell
end

# Collect static files
if test $env_mode = prod
    echo "📦 Collecting static files..."
    python manage.py collectstatic --noinput --clear
else if not test -d staticfiles
    echo "📦 Collecting static files (first run)..."
    python manage.py collectstatic --noinput --clear
end

# Start Daphne (ASGI server with WebSocket support)
echo ""
echo "✅ Server starting ($env_mode mode, DEBUG=$DJANGO_DEBUG)..."
echo "🌐 Web:   http://localhost:8888"
echo "🔐 Admin: http://localhost:8888/admin"
echo "💬 Login: admin / admin"
echo ""
echo "Press Ctrl+C to stop"
echo ""
daphne -b 0.0.0.0 -p 8888 onesimus.asgi:application
