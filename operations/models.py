from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone


class WorkStatus(models.TextChoices):
	"""Estados operacionais do assistente durante a sessão."""

	READY = "ready", "Ready"
	PAUSED = "paused", "Paused"
	OFFLINE = "offline", "Offline"


class WorkSession(models.Model):
	"""Representa uma sessão de trabalho aberta no login do utilizador."""

	user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="work_sessions")
	login_at = models.DateTimeField(default=timezone.now)
	logout_at = models.DateTimeField(null=True, blank=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-login_at"]
		constraints = [
			models.UniqueConstraint(
				fields=["user"],
				condition=Q(is_active=True),
				name="unique_active_work_session_per_user",
			)
		]

	def clean(self) -> None:
		if self.logout_at and self.logout_at < self.login_at:
			raise ValidationError({"logout_at": "O logout não pode ser anterior ao login."})
		if self.logout_at is not None and self.is_active:
			raise ValidationError(
				{"is_active": "Com logout_at definido, is_active deve ser False.", "logout_at": "Com is_active=True, logout_at deve ser None."}
			)

	@property
	def is_open(self) -> bool:
		return self.is_active and self.logout_at is None

	@property
	def duration_seconds(self) -> int:
		end_at = self.logout_at or timezone.now()
		return int((end_at - self.login_at).total_seconds())

	def __str__(self) -> str:
		return f"{self.user.username} @ {self.login_at:%Y-%m-%d %H:%M:%S}"


class WorkStatusLog(models.Model):
	"""Regista períodos contínuos de estado operacional por sessão."""

	user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="work_status_logs")
	session = models.ForeignKey(
		WorkSession,
		on_delete=models.PROTECT,
		related_name="status_logs",
	)
	status = models.CharField(max_length=20, choices=WorkStatus.choices)
	pause_request = models.ForeignKey(
		"breaks.PauseRequest",
		on_delete=models.PROTECT,
		related_name="work_status_logs",
		null=True,
		blank=True,
	)
	started_at = models.DateTimeField(default=timezone.now)
	ended_at = models.DateTimeField(null=True, blank=True)
	duration_seconds = models.PositiveIntegerField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-started_at"]
		constraints = [
			models.UniqueConstraint(
				fields=["user"],
				condition=Q(ended_at__isnull=True),
				name="unique_open_work_status_log_per_user",
			)
		]

	def clean(self) -> None:
		if self.ended_at and self.ended_at < self.started_at:
			raise ValidationError({"ended_at": "A data de fim não pode ser anterior ao início."})
		if self.status == WorkStatus.PAUSED and self.pause_request is None:
			raise ValidationError({"pause_request": "Estado paused exige um pedido de pausa."})
		if self.status != WorkStatus.PAUSED and self.pause_request is not None:
			raise ValidationError({"pause_request": "Só pode existir pedido de pausa no estado paused."})

	@property
	def is_open(self) -> bool:
		return self.ended_at is None

	@property
	def elapsed_seconds(self) -> int:
		end_at = self.ended_at or timezone.now()
		return int((end_at - self.started_at).total_seconds())

	def __str__(self) -> str:
		return f"{self.user.username} - {self.status} - {self.started_at:%Y-%m-%d %H:%M:%S}"
