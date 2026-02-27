#!/bin/bash
# Start Onesimus Web Application

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
WEB_DIR="$SCRIPT_DIR"

# --- Default values ---
env_mode=dev

# --- Usage ---
usage() {
    echo "Usage: run-web.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --dev    Development mode (default): DEBUG=true, requirements-dev.txt"
    echo "  --prod   Production mode: DEBUG=false, requirements-prod.txt"
    echo "  -h, --help  Show this help"
}

# --- Parse arguments ---
for arg in "$@"; do
    case "$arg" in
        --dev)  env_mode=dev ;;
        --prod) env_mode=prod ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $arg"; usage; exit 1 ;;
    esac
done

# --- Map mode to settings ---
if [ "$env_mode" = prod ]; then
    req_file=requirements-prod.txt
    export DJANGO_DEBUG=false
else
    req_file=requirements-dev.txt
    export DJANGO_DEBUG=true
fi

echo "🚀 Starting Onesimus Web Application ($env_mode mode)..."
echo "📁 Working directory: $WEB_DIR"
cd "$WEB_DIR"

# Activate venv
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Creating..."
    python3 -m venv .venv
    .venv/bin/pip install -U pip setuptools wheel
fi

echo "📦 Installing dependencies ($req_file)..."
.venv/bin/pip install -q -r "$req_file"

source .venv/bin/activate

# Run migrations if needed
echo "🔄 Running migrations..."
python manage.py migrate --noinput

# Create superuser if needed
if ! python manage.py shell -c "from django.contrib.auth.models import User; exit(0 if User.objects.filter(username='admin').exists() else 1)" 2>/dev/null; then
    echo "👤 Creating superuser 'admin' with password 'admin'..."
    echo "from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@example.local', 'admin')" | python manage.py shell
fi

# Collect static files
if [ "$env_mode" = prod ]; then
    echo "📦 Collecting static files..."
    python manage.py collectstatic --noinput --clear
elif [ ! -d "staticfiles" ]; then
    echo "📦 Collecting static files (first run)..."
    python manage.py collectstatic --noinput --clear
fi

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
