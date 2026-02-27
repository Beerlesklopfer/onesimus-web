"""URL configuration for jobs app."""
from django.urls import path
from . import views

app_name = 'jobs'

urlpatterns = [
    path('', views.jobs_list, name='list'),
    path('api/jobs/', views.jobs_api, name='api'),
    path('<int:job_id>/', views.job_detail, name='detail'),
    path('<int:job_id>/log/', views.job_log, name='log'),
]
