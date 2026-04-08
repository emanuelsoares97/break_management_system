"""
Views para gestão de pausas.

- POST views para ações de mutação
- GET views para listas e consulta
- Usa selectors para leitura
- Usa services para mutações
- Valida DomainError e comunica via messages
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import HttpResponseForbidden

from accounts.models import UserRole
from breaks.models import PauseType, PauseRequest
from breaks.services import (
	request_pause,
	approve_pause,
	reject_pause,
	finish_active_pause,
)
from dashboard.selectors import (
	get_pending_pause_requests_for_supervisor,
	get_pauses_for_today_for_supervisor,
)
from common.exceptions import DomainError
from dashboard.selectors import get_user_profile


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
# GET VIEWS
# ============================================================================


@login_required
def pending_pause_requests_view(request):
	"""
	Lista de pedidos de pausa pendentes para o supervisor.
	
	Enumera pausas com status=PENDING das equipas geridas.
	"""
	# Validar permissão
	perm_error = _require_role(request.user, UserRole.SUPERVISOR)
	if perm_error:
		return perm_error
	
	# Carregar dados
	pending_requests = get_pending_pause_requests_for_supervisor(request.user)
	
	context = {
		"pending_requests": pending_requests,
	}
	
	return render(request, "breaks/pending_pause_requests.html", context)


@login_required
def today_pause_requests_view(request):
	"""
	Lista de pausas do dia para o supervisor.
	
	Enumera todas as pausas de hoje (qualquer status) das equipas geridas.
	"""
	# Validar permissão
	perm_error = _require_role(request.user, UserRole.SUPERVISOR)
	if perm_error:
		return perm_error
	
	# Carregar dados
	today_pauses = get_pauses_for_today_for_supervisor(request.user)
	
	context = {
		"today_pauses": today_pauses,
	}
	
	return render(request, "breaks/today_pause_requests.html", context)


# ============================================================================
# POST VIEWS - AÇÕES
# ============================================================================


@login_required
@require_POST
def request_pause_view(request, pause_type_id):
	"""
	Pede uma pausa para o assistente.
	
	POST apenas.
	Redireciona para dashboard do assistente após sucesso.
	"""
	# Validar permissão
	perm_error = _require_role(request.user, UserRole.ASSISTANT)
	if perm_error:
		return perm_error
	
	# Obter tipo de pausa
	pause_type = get_object_or_404(PauseType, pk=pause_type_id)
	
	# Tentar pedir pausa
	try:
		request_pause(request.user, pause_type)
		messages.success(request, "Pause request submitted successfully.")
	except DomainError as e:
		messages.error(request, str(e))
	
	# Redirecionar
	return redirect("dashboard:assistant")


@login_required
@require_POST
def approve_pause_view(request, pause_request_id):
	"""
	Aprova uma pausa pendente.
	
	POST apenas.
	Supervisor apenas.
	Redireciona para lista de pendentes após sucesso.
	"""
	# Validar permissão
	perm_error = _require_role(request.user, UserRole.SUPERVISOR)
	if perm_error:
		return perm_error
	
	# Obter pausa
	pause_request = get_object_or_404(PauseRequest, pk=pause_request_id)
	
	# Tentar aprovar
	try:
		approve_pause(pause_request, request.user)
		messages.success(request, "Pause approved successfully.")
	except DomainError as e:
		messages.error(request, str(e))
	
	# Redirecionar
	return redirect("breaks:pending")


@login_required
@require_POST
def reject_pause_view(request, pause_request_id):
	"""
	Rejeita uma pausa pendente.
	
	POST apenas.
	Supervisor apenas.
	Lê motivo de rejeição de request.POST["reason"].
	Redireciona para lista de pendentes após sucesso.
	"""
	# Validar permissão
	perm_error = _require_role(request.user, UserRole.SUPERVISOR)
	if perm_error:
		return perm_error
	
	# Obter pausa e motivo
	pause_request = get_object_or_404(PauseRequest, pk=pause_request_id)
	reason = request.POST.get("reason", "")
	
	# Tentar rejeitar
	try:
		reject_pause(pause_request, request.user, reason=reason)
		messages.success(request, "Pause rejected successfully.")
	except DomainError as e:
		messages.error(request, str(e))
	
	# Redirecionar
	return redirect("breaks:pending")


@login_required
@require_POST
def finish_active_pause_view(request):
	"""
	Termina a pausa ativa do assistente.
	
	POST apenas.
	Assistant apenas.
	Redireciona para dashboard do assistente após sucesso.
	"""
	# Validar permissão
	perm_error = _require_role(request.user, UserRole.ASSISTANT)
	if perm_error:
		return perm_error
	
	# Tentar terminar pausa
	try:
		finish_active_pause(request.user)
		messages.success(request, "Active pause finished successfully.")
	except DomainError as e:
		messages.error(request, str(e))
	
	# Redirecionar
	return redirect("dashboard:assistant")
