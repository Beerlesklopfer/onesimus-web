# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

"""URL configuration for schedule app."""
from django.urls import path
from . import views

app_name = 'schedule'

urlpatterns = [
    path('', views.gantt_view, name='gantt'),
    path('weekly/', views.weekly_view, name='weekly'),
]
