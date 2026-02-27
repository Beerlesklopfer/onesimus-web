from django.urls import path
from . import views

app_name = 'common'

urlpatterns = [
    path('settings/', views.settings_api, name='settings'),
    path('preferences/', views.preferences_api, name='preferences'),
    path('about/', views.about_view, name='about'),
]
