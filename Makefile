# ── Onesimus Web — Makefile ───────────────────────────────────────────────────
#
# Development:   make dev
# Production:    make install && make migrate && make static
# Deployment:    make deploy       (install + migrate + static + restart)
# Service:       make start / stop / restart / status / logs
#
# Assumptions:
#   - virtualenv at .venv/
#   - systemd unit: contrib/onesimus.service  (sudo required for service commands)
#   - nginx config: contrib/onesimus.nginx.conf
#   - daphne binary at .venv/bin/daphne

.DEFAULT_GOAL := help
.PHONY: help venv install install-dev install-prod \
        install-system \
        migrate static superuser \
        dev run \
        deploy \
        start stop restart status logs \
        lint test clean

PY      := .venv/bin/python
PIP     := .venv/bin/pip
MANAGE  := $(PY) manage.py
SERVICE := onesimus
DEPLOY_DIR := $(shell pwd)
NGINX_AVAIL := /etc/nginx/sites-available/$(SERVICE)


# ── Virtualenv ────────────────────────────────────────────────────────────────

venv:                              ## Create virtualenv (if missing)
	@if [ ! -d .venv ]; then \
		python3 -m venv .venv; \
		$(PIP) install -q --upgrade pip setuptools wheel; \
		echo "  venv created."; \
	else \
		echo "  venv already exists."; \
	fi

install: venv                      ## Install production dependencies
	$(PIP) install -q -r requirements-prod.txt

install-dev: venv                  ## Install development dependencies
	$(PIP) install -q -r requirements-dev.txt

install-system:                    ## Install systemd unit + nginx config (requires sudo)
	@echo "  [systemd] installing contrib/onesimus.service …"
	sudo cp contrib/onesimus.service /etc/systemd/system/$(SERVICE).service
	sudo systemctl daemon-reload
	sudo systemctl enable $(SERVICE)
	@echo "  [systemd] $(SERVICE).service enabled."
	@echo ""
	@echo "  [nginx] copying contrib/onesimus.nginx.conf → $(NGINX_AVAIL) …"
	sudo cp contrib/onesimus.nginx.conf $(NGINX_AVAIL)
	@echo "  [nginx] config installed."
	@echo ""
	@echo "  ┌─────────────────────────────────────────────────────────────┐"
	@echo "  │  Manual steps required:                                     │"
	@echo "  │                                                             │"
	@echo "  │  1) Edit server_name in $(NGINX_AVAIL)"
	@echo "  │                                                             │"
	@echo "  │  2) Enable the nginx site:                                  │"
	@echo "  │       sudo ln -s $(NGINX_AVAIL) \\"
	@echo "  │                 /etc/nginx/sites-enabled/$(SERVICE)         │"
	@echo "  │       sudo nginx -t && sudo systemctl reload nginx          │"
	@echo "  │                                                             │"
	@echo "  │  3) Obtain TLS certificate:                                 │"
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

dev: install-dev migrate superuser ## Full dev setup + run daphne (DEBUG=true)
	DJANGO_DEBUG=true .venv/bin/daphne -b 0.0.0.0 -p 8888 onesimus.asgi:application

run:                               ## Run daphne (no setup, uses current env)
	.venv/bin/daphne -b 0.0.0.0 -p 8888 onesimus.asgi:application


# ── Deployment ────────────────────────────────────────────────────────────────

deploy: install migrate static     ## Full production deploy + service restart
	$(MAKE) restart
	@echo ""
	@echo "  Deployed. Service status:"
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

clean:                             ## Remove .venv, staticfiles, __pycache__
	rm -rf .venv staticfiles
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
