# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

from django.contrib import admin
from .models import Setting, UserPreference


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display  = ('key', 'value', 'description', 'updated_at')
    search_fields = ('key', 'description')
    ordering      = ('key',)
    readonly_fields = ('updated_at',)


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display  = ('user', 'scope', 'key', 'value', 'updated_at')
    list_filter   = ('scope', 'user')
    search_fields = ('user__username', 'scope', 'key')
    ordering      = ('user', 'scope', 'key')
    readonly_fields = ('updated_at',)
