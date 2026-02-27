# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

"""URL configuration for clients app."""
from django.urls import path
from . import views

app_name = 'clients'

urlpatterns = [
    path('', views.clients_list, name='list'),
    path('<int:client_id>/', views.client_detail, name='detail'),
]
