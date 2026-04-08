"""
URL config para breaks app.
"""

from django.urls import path
from breaks import views

app_name = "breaks"

urlpatterns = [
	path("pending/", views.pending_pause_requests_view, name="pending"),
	path("today/", views.today_pause_requests_view, name="today"),
	path("request/<int:pause_type_id>/", views.request_pause_view, name="request"),
	path("approve/<int:pause_request_id>/", views.approve_pause_view, name="approve"),
	path("reject/<int:pause_request_id>/", views.reject_pause_view, name="reject"),
	path("finish-active/", views.finish_active_pause_view, name="finish-active"),
]
