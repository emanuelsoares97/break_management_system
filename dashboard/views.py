"""
Views para o dashboard de utilizadores.

- Views sempre requerem login
- Permissões específicas por papel (role)
- Usa selectors para leitura
- Usa services para mutações
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from accounts.models import UserRole
from dashboard.selectors import (
	get_dashboard_snapshot_for_assistant,
	get_dashboard_snapshot_for_supervisor,
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
