"""URL configuration for storage app."""
from django.urls import path
from . import views

app_name = 'storage'

urlpatterns = [
    path('', views.storage_view, name='list'),
]
