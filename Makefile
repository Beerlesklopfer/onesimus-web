# ── Onesimus Web — Makefile ───────────────────────────────────────────────────
#
# Server setup (once):
#   git clone <repo> /root/onesimus-web && cd /root/onesimus-web
#   sudo make sysdeps        (libpq-dev, python3-dev — build deps)
#   sudo make install-system (systemd unit + nginx config + env template)
#   sudo make update         (creates /srv/onesimus-web, venv, pip, migrate, static, start)
#   make superuser           (create admin user — once only)
#
# Re-update after git pull:
#   sudo make update         (install + migrate + static + restart)
#
# Service:     make start / stop / restart / status / logs
# Development: make dev
#
# All production targets install into /srv/onesimus-web.

.DEFAULT_GOAL := help
.PHONY: help venv sysdeps install install-dev \
        install-system \
        migrate static superuser mockdata \
        dev run \
        update \
        start stop restart status logs \
        lint test clean
# $(DEPLOY_DIR) is a real file target — make creates it implicitly if missing

DEPLOY_DIR  := /srv/onesimus-web
PY          := $(DEPLOY_DIR)/.venv/bin/python
PIP         := $(DEPLOY_DIR)/.venv/bin/pip
MANAGE      := $(PY) manage.py
SERVICE     := onesimus
NGINX_NAME  := onesimus-web
NGINX_AVAIL := /etc/nginx/sites-available/$(NGINX_NAME)


# ── System dependencies ───────────────────────────────────────────────────────

sysdeps:                           ## Install system build dependencies (requires sudo)
	sudo apt-get install -y libpq-dev python3-dev


# ── Virtualenv ────────────────────────────────────────────────────────────────

$(DEPLOY_DIR):                     # create update dir with correct ownership (implicit)
	sudo mkdir -p $(DEPLOY_DIR)
	sudo chown www-data:www-data $(DEPLOY_DIR)

venv: $(DEPLOY_DIR)               ## Create virtualenv at $(DEPLOY_DIR)/.venv
	@if [ ! -d "$(DEPLOY_DIR)/.venv" ]; then \
		python3 -m venv $(DEPLOY_DIR)/.venv; \
		$(PIP) install -q --upgrade pip setuptools wheel; \
		echo "  venv created at $(DEPLOY_DIR)/.venv"; \
	else \
		echo "  venv already exists."; \
	fi

install: venv                      ## Install prod deps (creates update dir + venv implicitly)
	$(PIP) install -q -r requirements-prod.txt

install-dev:                       ## Install dev dependencies into local .venv
	@if [ ! -d .venv ]; then \
		python3 -m venv .venv; \
		.venv/bin/pip install -q --upgrade pip setuptools wheel; \
		echo "  dev venv created."; \
	fi
	.venv/bin/pip install -q -r requirements-dev.txt

install-system: $(DEPLOY_DIR)      ## Install systemd unit + nginx config (requires sudo)
	@echo "  [env] creating /etc/onesimus/ …"
	sudo mkdir -p /etc/onesimus
	@if [ ! -f /etc/onesimus/onesimus.env ]; then \
		printf 'DJANGO_SECRET_KEY=change-me-to-a-random-50-char-string\nDJANGO_ALLOWED_HOSTS=localhost,127.0.0.1\nDJANGO_DEBUG=false\nDATABASE_URL=sqlite:////srv/onesimus-web/db.sqlite3\n' \
			| sudo tee /etc/onesimus/onesimus.env > /dev/null; \
		echo "  [env] template written → /etc/onesimus/onesimus.env (edit before starting!)"; \
	else \
		echo "  [env] /etc/onesimus/onesimus.env already exists, skipping."; \
	fi
	@echo "  [systemd] installing contrib/onesimus.service …"
	sudo cp contrib/onesimus.service /etc/systemd/system/$(SERVICE).service
	sudo systemctl daemon-reload
	sudo systemctl enable $(SERVICE)
	@echo "  [systemd] $(SERVICE).service enabled."
	@echo ""
	@echo "  [nginx] copying contrib/onesimus.nginx.conf → $(NGINX_AVAIL) …"
	sudo cp contrib/onesimus-web.nginx.conf $(NGINX_AVAIL)
	@echo "  [nginx] config installed."
	@echo ""
	@echo "  ┌─────────────────────────────────────────────────────────────┐"
	@echo "  │  Manual steps required:                                     │"
	@echo "  │                                                             │"
	@echo "  │  1) Edit /etc/onesimus/onesimus.env (SECRET_KEY, DB, …)    │"
	@echo "  │                                                             │"
	@echo "  │  2) Edit server_name in $(NGINX_AVAIL)"
	@echo "  │                                                             │"
	@echo "  │  3) Enable the nginx site:                                  │"
	@echo "  │       sudo ln -s $(NGINX_AVAIL) \\"
	@echo "  │                 /etc/nginx/sites-enabled/$(SERVICE)         │"
	@echo "  │       sudo nginx -t && sudo systemctl reload nginx          │"
	@echo "  │                                                             │"
	@echo "  │  4) Obtain TLS certificate:                                 │"
	@echo "  │       sudo certbot --nginx -d <your-domain>                 │"
	@echo "  └─────────────────────────────────────────────────────────────┘"
	@echo ""


# ── Django ────────────────────────────────────────────────────────────────────

migrate:                           ## Apply database migrations
	$(MANAGE) migrate --noinput

static:                            ## Collect static files
	$(MANAGE) collectstatic --noinput --clear

superuser:                         ## Create admin superuser (admin/admin) if missing
	@$(MANAGE) shell -c "\
from django.contrib.auth.models import User; \
User.objects.filter(username='admin').exists() \
  or User.objects.create_superuser('admin','admin@example.local','admin')" \
	&& echo "  superuser ready (admin / admin)"

mockdata:                          ## Populate mock data (jobs, schedules, filesets)
	$(MANAGE) populate_mockups --clear
	$(MANAGE) populate_job_history --clear --days 120
	$(MANAGE) populate_job_filesets --clear
	$(MANAGE) populate_mock_schedules --clear


# ── Development server ────────────────────────────────────────────────────────

dev: install-dev                   ## Full dev setup + run daphne locally (DEBUG=true, uses .venv)
	.venv/bin/python manage.py migrate --noinput
	@.venv/bin/python manage.py shell -c "\
from django.contrib.auth.models import User; \
User.objects.filter(username='admin').exists() \
  or User.objects.create_superuser('admin','admin@example.local','admin')" \
	&& echo "  superuser ready (admin / admin)"
	DJANGO_DEBUG=true .venv/bin/daphne -b 0.0.0.0 -p 8888 onesimus.asgi:application

run:                               ## Run daphne from $(DEPLOY_DIR) (no setup)
	$(DEPLOY_DIR)/.venv/bin/daphne -b 0.0.0.0 -p 8888 onesimus.asgi:application


# ── Deployment ────────────────────────────────────────────────────────────────

update: install migrate static     ## Install deps + migrate + collectstatic + restart
	$(MAKE) restart
	@echo ""
	@echo "  Updated. Service status:"
	@systemctl status $(SERVICE) --no-pager -l || true


# ── systemd service ───────────────────────────────────────────────────────────

start:                             ## Start onesimus systemd service
	sudo systemctl start $(SERVICE)

stop:                              ## Stop onesimus systemd service
	sudo systemctl stop $(SERVICE)

restart:                           ## Restart onesimus systemd service
	sudo systemctl restart $(SERVICE)

status:                            ## Show onesimus service status
	systemctl status $(SERVICE) --no-pager -l

logs:                              ## Follow onesimus service journal
	journalctl -u $(SERVICE) -f --no-pager


# ── QA ────────────────────────────────────────────────────────────────────────

lint:                              ## Run ruff linter
	.venv/bin/ruff check .

test:                              ## Run Django test suite
	$(MANAGE) test --verbosity=2


# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:                             ## Remove $(DEPLOY_DIR)/.venv, staticfiles, __pycache__
	rm -rf $(DEPLOY_DIR)/.venv $(DEPLOY_DIR)/staticfiles
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true


# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  Onesimus Web — available targets"
	@echo ""
	@grep -E '^[a-z][a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":[^#]*## "} {printf "    make \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Production update dir: $(DEPLOY_DIR)"
	@echo ""
