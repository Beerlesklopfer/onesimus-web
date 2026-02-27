# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

from django.apps import AppConfig


class JobsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'jobs'
    verbose_name = 'Jobs Management'
