# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

from django.urls import path
from . import views

app_name = 'common'

urlpatterns = [
    path('settings/', views.settings_api, name='settings'),
    path('preferences/', views.preferences_api, name='preferences'),
    path('about/', views.about_view, name='about'),
    path('profile/', views.profile_view, name='profile'),
]
