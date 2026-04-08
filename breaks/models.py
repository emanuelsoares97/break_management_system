from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from teams.models import Team


class PauseRequestStatus(models.TextChoices):
	"""Estados possíveis de um pedido de pausa."""

	PENDING = "pending", "Pending"
	APPROVED = "approved", "Approved"
	REJECTED = "rejected", "Rejected"
	FINISHED = "finished", "Finished"


class PauseType(models.Model):
	"""Define um tipo de pausa disponível no sistema."""

	name = models.CharField(max_length=80, unique=True)
	code = models.CharField(max_length=30, unique=True)
	duration_minutes = models.PositiveIntegerField(validators=[MinValueValidator(1)])
	requires_approval = models.BooleanField(default=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["name"]

	@property
	def duration_display(self) -> str:
		return f"{self.duration_minutes} min"

	def __str__(self) -> str:
		return f"{self.name} ({self.code})"


class PauseRequest(models.Model):
	"""Regista o ciclo completo de um pedido de pausa."""

	user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="pause_requests")
	team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="pause_requests")
	session = models.ForeignKey(
		"operations.WorkSession",
		on_delete=models.PROTECT,
		related_name="pause_requests",
	)
	pause_type = models.ForeignKey(
		PauseType,
		on_delete=models.PROTECT,
		related_name="pause_requests",
	)
	status = models.CharField(
		max_length=20,
		choices=PauseRequestStatus.choices,
		default=PauseRequestStatus.PENDING,
	)
	requested_at = models.DateTimeField(default=timezone.now)
	approved_at = models.DateTimeField(null=True, blank=True)
	approved_by = models.ForeignKey(
		User,
		on_delete=models.PROTECT,
		related_name="approved_pause_requests",
		null=True,
		blank=True,
	)
	rejected_at = models.DateTimeField(null=True, blank=True)
	rejected_by = models.ForeignKey(
		User,
		on_delete=models.PROTECT,
		related_name="rejected_pause_requests",
		null=True,
		blank=True,
	)
	started_at = models.DateTimeField(null=True, blank=True)
	ended_at = models.DateTimeField(null=True, blank=True)
	duration_seconds = models.PositiveIntegerField(null=True, blank=True)
	is_over_limit = models.BooleanField(default=False)
	rejection_reason = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-requested_at"]
		constraints = [
			models.UniqueConstraint(
				fields=["user"],
				condition=Q(status=PauseRequestStatus.PENDING),
				name="unique_pending_pause_request_per_user",
			),
			models.UniqueConstraint(
				fields=["user"],
				condition=Q(status=PauseRequestStatus.APPROVED, ended_at__isnull=True),
				name="unique_active_pause_per_user",
			),
		]

	def clean(self) -> None:
		if self.approved_at and self.rejected_at:
			raise ValidationError("Um pedido não pode estar aprovado e rejeitado ao mesmo tempo.")
		if self.approved_by and self.rejected_by:
			raise ValidationError("Um pedido não pode ter aprovador e rejeitador ao mesmo tempo.")
		if self.status == PauseRequestStatus.APPROVED and not self.approved_at:
			raise ValidationError({"approved_at": "Estado approved exige approved_at."})
		if self.status == PauseRequestStatus.REJECTED and not self.rejected_at:
			raise ValidationError({"rejected_at": "Estado rejected exige rejected_at."})
		if self.status == PauseRequestStatus.FINISHED and (not self.started_at or not self.ended_at):
			raise ValidationError({"status": "Estado finished exige started_at e ended_at."})
		if self.approved_by and not self.approved_at:
			raise ValidationError({"approved_at": "approved_by exige approved_at."})
		if self.rejected_by and not self.rejected_at:
			raise ValidationError({"rejected_at": "rejected_by exige rejected_at."})
		if self.started_at and self.ended_at and self.ended_at < self.started_at:
			raise ValidationError({"ended_at": "A data de fim não pode ser anterior ao início."})

	@property
	def is_pending(self) -> bool:
		return self.status == PauseRequestStatus.PENDING

	@property
	def is_active(self) -> bool:
		return self.status == PauseRequestStatus.APPROVED and self.ended_at is None

	@property
	def is_finished(self) -> bool:
		return self.status == PauseRequestStatus.FINISHED

	def __str__(self) -> str:
		return f"{self.user.username} - {self.pause_type.code} - {self.status}"
