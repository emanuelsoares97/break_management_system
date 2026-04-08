"""
Selectors para relatórios.

Funções de leitura/consulta apenas.
Sem mutações de estado.
Sem chamadas a services.
Base inicial para suportar relatórios futuros.
"""

from datetime import date
from typing import Optional

from django.contrib.auth.models import User
from django.db.models import QuerySet

from breaks.models import PauseRequest
from operations.models import WorkSession


# ============================================================================
# SELECTORS PÚBLICOS
# ============================================================================


def get_work_sessions_for_user_between(
	user: User,
	start_date: date,
	end_date: date,
) -> QuerySet:
	"""
	Devolve queryset de WorkSession do utilizador entre duas datas.

	Filtra por login_at >= start_date e login_at <= end_date.

	Útil para histórico de logs de trabalho, relatórios de tempo-presença, etc.
	"""
	return WorkSession.objects.filter(
		user=user,
		login_at__date__gte=start_date,
		login_at__date__lte=end_date,
	).select_related("user").order_by("-login_at")


def get_pause_requests_for_user_between(
	user: User,
	start_date: date,
	end_date: date,
) -> QuerySet:
	"""
	Devolve queryset de PauseRequest do utilizador entre duas datas.

	Filtra por requested_at >= start_date e requested_at <= end_date.

	Útil para histórico de pausas, relatórios de comportamento, etc.
	"""
	return PauseRequest.objects.filter(
		user=user,
		requested_at__date__gte=start_date,
		requested_at__date__lte=end_date,
	).select_related(
		"user",
		"team",
		"pause_type",
		"session",
		"approved_by",
		"rejected_by",
	).order_by("-requested_at")
