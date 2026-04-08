from django.contrib import admin

from breaks.models import PauseRequest, PauseType


@admin.action(description="Ativar tipos de pausa selecionados")
def activate_pause_types(modeladmin, request, queryset):
	queryset.update(is_active=True)


@admin.action(description="Desativar tipos de pausa selecionados")
def deactivate_pause_types(modeladmin, request, queryset):
	queryset.update(is_active=False)


@admin.register(PauseType)
class PauseTypeAdmin(admin.ModelAdmin):
	list_display = (
		"name",
		"code",
		"duration_minutes",
		"requires_approval",
		"is_active",
		"created_at",
	)
	list_filter = ("requires_approval", "is_active")
	search_fields = ("name", "code")
	ordering = ("name",)
	readonly_fields = ("created_at", "updated_at")
	actions = (activate_pause_types, deactivate_pause_types)


@admin.register(PauseRequest)
class PauseRequestAdmin(admin.ModelAdmin):
	list_display = (
		"user",
		"team",
		"pause_type",
		"status",
		"requested_at",
		"approved_at",
		"approved_by",
		"started_at",
		"ended_at",
		"is_over_limit",
	)
	list_filter = (
		"status",
		"pause_type",
		"team",
		"is_over_limit",
		"requested_at",
	)
	search_fields = (
		"user__username",
		"user__first_name",
		"user__last_name",
		"team__name",
		"pause_type__name",
		"pause_type__code",
	)
	ordering = ("-requested_at",)
	readonly_fields = ("created_at", "updated_at", "duration_seconds")
	date_hierarchy = "requested_at"
	list_select_related = (
		"user",
		"team",
		"pause_type",
		"approved_by",
		"rejected_by",
		"session",
	)
	autocomplete_fields = (
		"user",
		"team",
		"session",
		"pause_type",
		"approved_by",
		"rejected_by",
	)
