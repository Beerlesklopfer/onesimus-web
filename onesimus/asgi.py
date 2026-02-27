# SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
# SPDX-License-Identifier: MIT

"""
ASGI config for onesimus project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'onesimus.settings')

django_asgi_app = get_asgi_application()

# Import consumers after Django is initialized
from common.consumers import NotificationConsumer
from jobs.consumers import JobsConsumer
from clients.consumers import ClientsConsumer
from schedules.consumers import SchedulesConsumer

websocket_urlpatterns = [
    path('ws/notifications/', NotificationConsumer.as_asgi()),
    path('ws/jobs/updates/', JobsConsumer.as_asgi()),
    path('ws/clients/updates/', ClientsConsumer.as_asgi()),
    path('ws/schedules/updates/', SchedulesConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
