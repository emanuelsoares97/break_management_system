"""
Views para autenticação e gestão de sessão de utilizador.

- Login: autentica + inicia WorkSession
- Logout: fecha WorkSession + faz logout
- Redirecionamento por role
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages

from accounts.models import UserRole
from operations.services import start_work_session, end_work_session
from common.exceptions import DomainError
from dashboard.selectors import get_user_profile


# ============================================================================
# HELPERS
# ============================================================================


def _get_dashboard_redirect_for_user(user):
	"""
	Devolve o nome da view de dashboard correto para o utilizador.
	
	Baseado no role do userprofile:
	- ASSISTANT -> dashboard:assistant
	- SUPERVISOR -> dashboard:supervisor
	- sem profile ou role desconhecido -> None (redireciona para login)
	"""
	profile = get_user_profile(user)
	if profile is None:
		return None
	
	if profile.role == UserRole.ASSISTANT:
		return "dashboard:assistant"
	elif profile.role == UserRole.SUPERVISOR:
		return "dashboard:supervisor"
	
	# Role desconhecido
	return None


# ============================================================================
# VIEWS PÚBLICAS
# ============================================================================


def login_view(request):
	"""
	View de login.
	
	GET: apresenta form de login
	POST: autentica e inicia WorkSession
	
	Se sucesso: redireciona para dashboard conforme role
	Se erro: mostra mensagem e volta ao form
	"""
	if request.method == "POST":
		username = request.POST.get("username", "").strip()
		password = request.POST.get("password", "").strip()
		
		# Tentar autenticar
		user = authenticate(request, username=username, password=password)
		
		if user is None:
			messages.error(request, "Invalid username or password.")
			return render(request, "accounts/login.html")
		
		# Autenticação bem-sucedida
		# Tentar iniciar sessão de trabalho
		try:
			start_work_session(user)
		except DomainError as e:
			# Se há erro ao abrir sessão, fazer logout do Django
			# para não deixar sessão de auth aberta sem WorkSession
			messages.error(request, f"Failed to start work session: {str(e)}")
			return render(request, "accounts/login.html")
		
		# Fazer login Django
		login(request, user)
		
		# Redirecionar para dashboard correto
		dashboard_url = _get_dashboard_redirect_for_user(user)
		if dashboard_url:
			return redirect(dashboard_url)
		else:
			# Se não tem profile/role válido, logout e volta ao login
			logout(request)
			messages.error(request, "User profile is invalid.")
			return redirect("accounts:login")
	
	# GET: mostrar form
	return render(request, "accounts/login.html")


@login_required(login_url="accounts:login")
@require_POST
def logout_view(request):
	"""
	View de logout.
	
	POST apenas.
	Fecha WorkSession e faz logout Django.
	
	Redireciona para login.
	"""
	# Tentar fechar sessão de trabalho
	try:
		end_work_session(request.user)
	except DomainError as e:
		# Se há erro ao fechar sessão (e.g., nenhuma sessão ativa),
		# ainda assim fazemos logout Django por segurança.
		# O utilizador pode ter sessions antigas/orphans.
		messages.warning(
			request,
			f"Warning: could not properly close work session. {str(e)}"
		)
	
	# Fazer logout Django
	logout(request)
	
	# Mensagem de sucesso
	messages.success(request, "You have been logged out successfully.")
	
	# Redirecionar para login
	return redirect("accounts:login")


def home_redirect_view(request):
	"""
	View para root ("/").
	
	Se utilizador autenticado: redireciona para dashboard correto
	Senão: redireciona para login
	"""
	if request.user.is_authenticated:
		# Redirecionar para dashboard conforme role
		dashboard_url = _get_dashboard_redirect_for_user(request.user)
		if dashboard_url:
			return redirect(dashboard_url)
		else:
			# Perfil inválido, vai para login
			logout(request)
			return redirect("accounts:login")
	else:
		# Não autenticado, vai para login
		return redirect("accounts:login")

