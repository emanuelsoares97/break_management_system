"""
Selectors para dashboard.

Funções de leitura/consulta apenas.
Sem mutações de estado.
Sem chamadas a services.
Otimizadas com select_related / prefetch_related.
"""

from datetime import date
from typing import Optional, Dict, List, Any

from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import QuerySet, Prefetch

from accounts.models import UserProfile, UserRole, SupervisorTeam
from teams.models import Team
from breaks.models import PauseRequest, PauseRequestStatus, PauseType
from operations.models import WorkSession, WorkStatusLog, WorkStatus


# ============================================================================
# HELPERS PRIVADOS
# ============================================================================


def _get_today_range() -> tuple[Any, Any]:
	"""
	Devolve o intervalo de tempo para o dia de hoje (timezone-aware, local).

	Retorna (start_datetime, end_datetime) para a data local.
	"""
	today = timezone.localdate()
	start_of_day = timezone.make_aware(
		timezone.datetime.combine(today, timezone.time.min)
	)
	end_of_day = timezone.make_aware(
		timezone.datetime.combine(today, timezone.time.max)
	)
	return start_of_day, end_of_day


# ============================================================================
# SELECTORS PÚBLICOS
# ============================================================================


def get_user_profile(user: User) -> Optional[UserProfile]:
	"""
	Devolve o UserProfile do utilizador, ou None se não existir.

	Útil para validação rápida; para dados complexos,
	usar get_dashboard_snapshot_for_assistant ou similar.
	"""
	try:
		return user.profile
	except UserProfile.DoesNotExist:
		return None


def get_supervisor_team_ids(supervisor: User) -> List[int]:
	"""
	Devolve a lista de IDs de equipas geridas pelo supervisor.

	Assume que 'supervisor' é um utilizador com role=SUPERVISOR.
	"""
	profile = get_user_profile(supervisor)
	if not profile:
		return []

	return list(
		SupervisorTeam.objects.filter(supervisor_profile=profile).values_list(
			"team_id", flat=True
		)
	)


def get_logged_in_assistants_for_supervisor(supervisor: User) -> QuerySet:
	"""
	Devolve queryset de WorkSession com assistentes ativos
	das equipas geridas pelo supervisor.

	Retorna WorkSession (is_active=True) com select_related para:
	- user
	- user.profile
	- user.profile.team

	Útil para a tabela da supervisão mostrar assistentes logados.
	"""
	team_ids = get_supervisor_team_ids(supervisor)
	if not team_ids:
		return WorkSession.objects.none()

	return WorkSession.objects.filter(
		is_active=True,
		user__profile__team_id__in=team_ids,
		user__profile__role=UserRole.ASSISTANT,
	).select_related(
		"user",
		"user__profile",
		"user__profile__team",
	).order_by("-login_at")


def get_current_status_log_for_user(user: User) -> Optional[WorkStatusLog]:
	"""
	Devolve o WorkStatusLog aberto (ended_at=None) do utilizador.

	Assume que há apenas um aberto simultaneamente (constraint na BD).
	Devolve None se não existir sessão ativa ou nenhum status log aberto.
	"""
	return WorkStatusLog.objects.filter(
		user=user,
		ended_at__isnull=True,
	).select_related(
		"session",
		"pause_request",
	).first()


def get_pending_pause_requests_for_supervisor(supervisor: User) -> QuerySet:
	"""
	Devolve queryset de PauseRequest com status=PENDING
	das equipas geridas pelo supervisor.

	Ordenação: mais recentes primeiro (requested_at DESC).
	Com select_related para user, team, pause_type, session.
	"""
	team_ids = get_supervisor_team_ids(supervisor)
	if not team_ids:
		return PauseRequest.objects.none()

	return PauseRequest.objects.filter(
		team_id__in=team_ids,
		status=PauseRequestStatus.PENDING,
	).select_related(
		"user",
		"team",
		"pause_type",
		"session",
	).order_by("-requested_at")


def get_pauses_for_today_for_supervisor(supervisor: User) -> QuerySet:
	"""
	Devolve queryset de PauseRequest do dia de hoje
	das equipas geridas pelo supervisor.

	Inclui: pendentes, aprovadas, rejeitadas, concluídas.
	Ordenação: mais recentes primeiro.
	Com select_related para user, team, pause_type.
	"""
	team_ids = get_supervisor_team_ids(supervisor)
	if not team_ids:
		return PauseRequest.objects.none()

	start_of_day, end_of_day = _get_today_range()

	return PauseRequest.objects.filter(
		team_id__in=team_ids,
		requested_at__gte=start_of_day,
		requested_at__lte=end_of_day,
	).select_related(
		"user",
		"team",
		"pause_type",
	).order_by("-requested_at")


def get_active_pause_for_user(user: User) -> Optional[PauseRequest]:
	"""
	Devolve a pausa ativa (status=APPROVED, ended_at=None) do utilizador.

	Há apenas uma por constraint na BD.
	Devolve None se o utilizador não tem pausa ativa.
	"""
	return PauseRequest.objects.filter(
		user=user,
		status=PauseRequestStatus.APPROVED,
		ended_at__isnull=True,
	).select_related(
		"pause_type",
		"team",
	).first()


def get_available_pause_types() -> QuerySet:
	"""
	Devolve queryset de PauseType ativos, ordenados por nome.

	Útil para o dropdown do dashboard do assistente.
	"""
	return PauseType.objects.filter(is_active=True).order_by("name")


def get_active_work_session_for_user(user: User) -> Optional[WorkSession]:
	"""
	Devolve a sessão de trabalho ativa (is_active=True) do utilizador.

	Há apenas uma por constraint na BD.
	Devolve None se o utilizador não tem sessão ativa.
	"""
	return WorkSession.objects.filter(
		user=user,
		is_active=True,
	).select_related("user").first()


def get_dashboard_snapshot_for_assistant(user: User) -> Dict[str, Any]:
	"""
	Devolve snapshot simplificado para o dashboard do assistente.

	Estrutura do dict:
	{
		'profile': UserProfile ou None,
		'active_session': WorkSession ou None,
		'current_status_log': WorkStatusLog ou None,
		'active_pause': PauseRequest ou None,
		'available_pause_types': QuerySet de PauseType,
	}

	Útil para consumir facilmente em views do assistente.
	"""
	profile = get_user_profile(user)
	active_session = get_active_work_session_for_user(user)
	current_status_log = get_current_status_log_for_user(user)
	active_pause = get_active_pause_for_user(user)
	available_pause_types = get_available_pause_types()

	return {
		"profile": profile,
		"active_session": active_session,
		"current_status_log": current_status_log,
		"active_pause": active_pause,
		"available_pause_types": available_pause_types,
	}


def get_dashboard_snapshot_for_supervisor(supervisor: User) -> Dict[str, Any]:
	"""
	Devolve snapshot simplificado para o dashboard da supervisão.

	Estrutura do dict:
	{
		'profile': UserProfile ou None,
		'managed_team_ids': list de team IDs,
		'logged_in_assistants': QuerySet de WorkSession,
		'pending_pause_requests': QuerySet de PauseRequest,
		'pauses_today': QuerySet de PauseRequest,
	}

	Útil para consumir facilmente em views de supervisão.
	"""
	profile = get_user_profile(supervisor)
	managed_team_ids = get_supervisor_team_ids(supervisor)
	logged_in_assistants = get_logged_in_assistants_for_supervisor(supervisor)
	pending_pause_requests = get_pending_pause_requests_for_supervisor(supervisor)
	pauses_today = get_pauses_for_today_for_supervisor(supervisor)

	return {
		"profile": profile,
		"managed_team_ids": managed_team_ids,
		"logged_in_assistants": logged_in_assistants,
		"pending_pause_requests": pending_pause_requests,
		"pauses_today": pauses_today,
	}
