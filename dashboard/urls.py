"""
URL config para dashboard app.
"""

from django.urls import path
from dashboard import views

app_name = "dashboard"

urlpatterns = [
	path("assistant/", views.assistant_dashboard_view, name="assistant"),
	path("supervisor/", views.supervisor_dashboard_view, name="supervisor"),
]
