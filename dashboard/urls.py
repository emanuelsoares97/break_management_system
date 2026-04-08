"""
URL config para dashboard app.
"""

from django.urls import path
from dashboard import views

app_name = "dashboard"

urlpatterns = [
	path("assistant/", views.assistant_dashboard_view, name="assistant"),
	path("assistant/poll/", views.assistant_dashboard_poll_view, name="assistant-poll"),
	path("supervisor/", views.supervisor_dashboard_view, name="supervisor"),
	path("supervisor/poll/", views.supervisor_dashboard_poll_view, name="supervisor-poll"),
]
