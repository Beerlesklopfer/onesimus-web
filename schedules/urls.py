"""URL configuration for schedule app."""
from django.urls import path
from . import views

app_name = 'schedule'

urlpatterns = [
    path('', views.gantt_view, name='gantt'),
    path('weekly/', views.weekly_view, name='weekly'),
]
