from django.contrib import admin

from operations.models import WorkSession, WorkStatusLog


@admin.register(WorkSession)
class WorkSessionAdmin(admin.ModelAdmin):
	list_display = (
		"user",
		"login_at",
		"logout_at",
		"is_active",
		"session_duration_seconds",
		"created_at",
	)
	list_filter = ("is_active", "login_at")
	search_fields = ("user__username", "user__first_name", "user__last_name")
	ordering = ("-login_at",)
	readonly_fields = ("created_at", "updated_at")
	date_hierarchy = "login_at"
	list_select_related = ("user",)
	autocomplete_fields = ("user",)

	@admin.display(description="duration (s)")
	def session_duration_seconds(self, obj):
		return obj.duration_seconds


@admin.register(WorkStatusLog)
class WorkStatusLogAdmin(admin.ModelAdmin):
	list_display = (
		"user",
		"status",
		"pause_request",
		"started_at",
		"ended_at",
		"elapsed_seconds",
	)
	list_filter = ("status", "started_at")
	search_fields = ("user__username", "user__first_name", "user__last_name")
	ordering = ("-started_at",)
	readonly_fields = ("created_at", "updated_at", "duration_seconds")
	date_hierarchy = "started_at"
	list_select_related = ("user", "session", "pause_request")
	autocomplete_fields = ("user", "session", "pause_request")

	@admin.display(description="duration (s)")
	def elapsed_seconds(self, obj):
		return obj.elapsed_seconds
