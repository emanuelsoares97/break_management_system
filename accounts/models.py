from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from teams.models import Team


class UserRole(models.TextChoices):
	"""Perfis de acesso disponíveis no sistema."""

	ASSISTANT = "assistant", "Assistant"
	SUPERVISOR = "supervisor", "Supervisor"


class UserProfile(models.Model):
	"""Extensão do utilizador com contexto operacional."""

	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
	team = models.ForeignKey(
		Team,
		on_delete=models.SET_NULL,
		related_name="profiles",
		null=True,
		blank=True,
	)
	role = models.CharField(max_length=20, choices=UserRole.choices)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["user__first_name", "user__last_name", "user__username"]

	def __str__(self) -> str:
		if self.user.get_full_name():
			return f"{self.user.get_full_name()} ({self.role})"
		return f"{self.user.username} ({self.role})"


class SupervisorTeam(models.Model):
	"""Relaciona supervisores com as equipas que podem acompanhar."""

	supervisor_profile = models.ForeignKey(
		UserProfile,
		on_delete=models.CASCADE,
		related_name="supervised_teams",
	)
	team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="supervisors")
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["team__name", "supervisor_profile__user__username"]
		constraints = [
			models.UniqueConstraint(
				fields=["supervisor_profile", "team"],
				name="unique_supervisor_team_assignment",
			)
		]

	def clean(self) -> None:
		if self.supervisor_profile.role != UserRole.SUPERVISOR:
			raise ValidationError({"supervisor_profile": "O profile tem de ser supervisor."})

	def __str__(self) -> str:
		return f"{self.supervisor_profile} -> {self.team}"
