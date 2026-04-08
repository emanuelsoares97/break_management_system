from django.contrib import admin

from accounts.models import SupervisorTeam, UserProfile, UserRole


class SupervisorTeamInline(admin.TabularInline):
	model = SupervisorTeam
	fk_name = "supervisor_profile"
	extra = 0
	autocomplete_fields = ("team",)
	readonly_fields = ("created_at",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "team", "role", "is_active", "created_at")
	list_filter = ("role", "is_active", "team")
	search_fields = (
		"user__username",
		"user__first_name",
		"user__last_name",
		"team__name",
	)
	ordering = ("user__first_name", "user__last_name", "user__username")
	readonly_fields = ("created_at", "updated_at")
	autocomplete_fields = ("user", "team")
	list_select_related = ("user", "team")

	def get_inlines(self, request, obj):
		if obj and obj.role == UserRole.SUPERVISOR:
			return (SupervisorTeamInline,)
		return ()


@admin.register(SupervisorTeam)
class SupervisorTeamAdmin(admin.ModelAdmin):
	list_display = ("supervisor_profile", "team", "created_at")
	list_filter = ("team",)
	search_fields = (
		"supervisor_profile__user__username",
		"supervisor_profile__user__first_name",
		"supervisor_profile__user__last_name",
		"team__name",
	)
	ordering = ("team__name", "supervisor_profile__user__username")
	readonly_fields = ("created_at",)
	autocomplete_fields = ("supervisor_profile", "team")
	list_select_related = ("supervisor_profile__user", "team")
