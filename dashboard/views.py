"""
Views para o dashboard de utilizadores.

- Views sempre requerem login
- Permissões específicas por papel (role)
- Usa selectors para leitura
- Usa services para mutações
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from datetime import timedelta

from accounts.models import UserRole
from dashboard.selectors import (
	get_dashboard_snapshot_for_assistant,
	get_dashboard_snapshot_for_supervisor,
	get_latest_pause_request_for_user,
	get_open_status_logs_for_users,
	get_pending_pause_request_for_user,
	get_user_profile,
)


# ============================================================================
# HELPERS DE PERMISSÃO
# ============================================================================


def _require_role(user, required_role):
	"""
	Valida se o utilizador tem o role requerido.
	
	Retorna None se OK, HttpResponseForbidden se Não permitido.
	"""
	profile = get_user_profile(user)
	if profile is None or profile.role != required_role:
		return HttpResponseForbidden("Não tem permissão para aceder a este recurso.")
	return None


# ============================================================================
# VIEWS PÚBLICAS
# ============================================================================


@login_required
def assistant_dashboard_view(request):
	"""
	Dashboard do assistente.
	
	Mostra:
	- estado atual (perfil, sessão, status log)
	- pausa ativa, se existir
	- tipos de pausa disponíveis
	"""
	# Validar permissão
	perm_error = _require_role(request.user, UserRole.ASSISTANT)
	if perm_error:
		return perm_error
	
	# Carregar dados
	snapshot = get_dashboard_snapshot_for_assistant(request.user)
	
	context = {
		"snapshot": snapshot,
	}
	
	return render(request, "dashboard/assistant_dashboard.html", context)


@login_required
def supervisor_dashboard_view(request):
	"""
	Dashboard da supervisão.
	
	Mostra:
	- assistentes logados
	- pedidos pendentes
	- pausas do dia
	"""
	# Validar permissão
	perm_error = _require_role(request.user, UserRole.SUPERVISOR)
	if perm_error:
		return perm_error
	
	# Carregar dados
	snapshot = get_dashboard_snapshot_for_supervisor(request.user)
	
	context = {
		"snapshot": snapshot,
	}
	
	return render(request, "dashboard/supervisor_dashboard.html", context)


@login_required
@require_GET
def assistant_dashboard_poll_view(request):
	"""
	Endpoint JSON para polling leve do dashboard de assistente.

	Atualiza:
	- estado atual
	- pausa ativa (incluindo timer)
	- pedido pendente/última decisão
	"""
	perm_error = _require_role(request.user, UserRole.ASSISTANT)
	if perm_error:
		return perm_error

	snapshot = get_dashboard_snapshot_for_assistant(request.user)
	active_pause = snapshot["active_pause"]
	pending_pause = get_pending_pause_request_for_user(request.user)
	latest_pause = get_latest_pause_request_for_user(request.user)
	current_status_log = snapshot["current_status_log"]

	active_pause_payload = None
	if active_pause:
		total_pause_seconds = active_pause.pause_type.duration_minutes * 60
		started_at = active_pause.started_at or active_pause.requested_at
		elapsed_seconds = int((timezone.now() - started_at).total_seconds())
		remaining_seconds = total_pause_seconds - elapsed_seconds

		active_pause_payload = {
			"id": active_pause.id,
			"pause_type": active_pause.pause_type.name,
			"started_at": timezone.localtime(started_at).strftime("%d/%m/%Y %H:%M"),
			"remaining_seconds": remaining_seconds,
		}

	pending_payload = None
	if pending_pause:
		pending_payload = {
			"id": pending_pause.id,
			"pause_type": pending_pause.pause_type.name,
			"requested_at": timezone.localtime(pending_pause.requested_at).strftime("%d/%m/%Y %H:%M"),
		}

	latest_payload = None
	if latest_pause:
		latest_payload = {
			"id": latest_pause.id,
			"status": latest_pause.status,
			"status_label": latest_pause.get_status_display(),
			"rejection_reason": latest_pause.rejection_reason,
		}

	payload = {
		"current_status": {
			"status": current_status_log.status if current_status_log else "unknown",
			"status_label": current_status_log.get_status_display() if current_status_log else "Unknown",
			"started_at": timezone.localtime(current_status_log.started_at).strftime("%H:%M") if current_status_log else None,
		},
		"active_pause": active_pause_payload,
		"pending_pause": pending_payload,
		"latest_pause": latest_payload,
	}

	return JsonResponse(payload)


@login_required
@require_GET
def supervisor_dashboard_poll_view(request):
	"""
	Endpoint JSON para polling leve do dashboard de supervisão.

	Atualiza:
	- cards de métricas
	- tabela de assistentes logados
	- preview de pedidos pendentes
	"""
	perm_error = _require_role(request.user, UserRole.SUPERVISOR)
	if perm_error:
		return perm_error

	snapshot = get_dashboard_snapshot_for_supervisor(request.user)

	logged_sessions = list(snapshot["logged_in_assistants"])
	pending_requests = list(snapshot["pending_pause_requests"])
	pauses_today = list(snapshot["pauses_today"])

	user_ids = [session.user_id for session in logged_sessions]
	open_status_logs = get_open_status_logs_for_users(user_ids)
	status_by_user_id = {log.user_id: log for log in open_status_logs}

	logged_in_assistants_payload = []
	for session in logged_sessions:
		status_log = status_by_user_id.get(session.user_id)
		status = status_log.status if status_log else "unknown"
		status_label = status_log.get_status_display() if status_log else "Unknown"
		pause_remaining_seconds = None
		pause_ends_at_iso = None

		if status_log and status == "paused" and status_log.pause_request and status_log.pause_request.started_at:
			pause_request = status_log.pause_request
			total_pause_seconds = pause_request.pause_type.duration_minutes * 60
			elapsed_seconds = int((timezone.now() - pause_request.started_at).total_seconds())
			pause_remaining_seconds = total_pause_seconds - elapsed_seconds
			pause_ends_at = pause_request.started_at + timedelta(seconds=total_pause_seconds)
			pause_ends_at_iso = timezone.localtime(pause_ends_at).isoformat()

		logged_in_assistants_payload.append(
			{
				"username": session.user.username,
				"full_name": session.user.get_full_name() or session.user.username,
				"team": getattr(session.user.profile.team, "name", "N/A"),
				"status": status,
				"status_label": status_label,
				"login_at": timezone.localtime(session.login_at).strftime("%d/%m/%Y %H:%M"),
				"pause_remaining_seconds": pause_remaining_seconds,
				"pause_ends_at_iso": pause_ends_at_iso,
			}
		)

	pending_preview_payload = []
	for pause in pending_requests[:5]:
		pending_preview_payload.append(
			{
				"id": pause.id,
				"username": pause.user.username,
				"full_name": pause.user.get_full_name() or pause.user.username,
				"team": pause.team.name,
				"pause_type": pause.pause_type.name,
				"requested_at": timezone.localtime(pause.requested_at).strftime("%d/%m/%Y %H:%M"),
			}
		)

	payload = {
		"stats": {
			"logged_in_assistants": len(logged_sessions),
			"pending_pause_requests": len(pending_requests),
			"pauses_today": len(pauses_today),
		},
		"logged_in_assistants": logged_in_assistants_payload,
		"pending_preview": pending_preview_payload,
	}

	return JsonResponse(payload)
