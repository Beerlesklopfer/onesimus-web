# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

"""URL configuration for storage app."""
from django.urls import path
from . import views

app_name = 'storage'

urlpatterns = [
    path('',                              views.storage_view,         name='list'),
    path('storage/<int:pk>/pools/',       views.storage_pools_htmx,  name='storage_pools'),
    path('storage/<int:pk>/stats/',       views.storage_stats_htmx,  name='storage_stats'),
    path('pool/<int:pk>/stats/',          views.pool_stats_htmx,     name='pool_stats'),
]
