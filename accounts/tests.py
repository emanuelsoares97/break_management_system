from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile, UserRole
from operations.models import WorkSession, WorkStatus, WorkStatusLog
from operations.services import start_work_session
from teams.models import Team


class AuthViewsTests(TestCase):
	def setUp(self):
		self.team = Team.objects.create(name="Retention Team")

		self.assistant = User.objects.create_user(
			username="assistant_auth",
			password="Test12345!",
		)
		UserProfile.objects.create(
			user=self.assistant,
			role=UserRole.ASSISTANT,
			team=self.team,
		)

		self.supervisor = User.objects.create_user(
			username="supervisor_auth",
			password="Test12345!",
		)
		UserProfile.objects.create(
			user=self.supervisor,
			role=UserRole.SUPERVISOR,
			team=self.team,
		)

	def test_valid_login_authenticates_creates_work_session_and_redirects_assistant(self):
		response = self.client.post(
			reverse("accounts:login"),
			data={"username": "assistant_auth", "password": "Test12345!"},
		)

		self.assertRedirects(response, reverse("dashboard:assistant"))
		self.assertIn("_auth_user_id", self.client.session)

		session = WorkSession.objects.get(user=self.assistant, is_active=True)
		open_log = WorkStatusLog.objects.get(user=self.assistant, session=session, ended_at__isnull=True)
		self.assertEqual(open_log.status, WorkStatus.READY)

	def test_valid_login_redirects_supervisor_to_supervisor_dashboard(self):
		response = self.client.post(
			reverse("accounts:login"),
			data={"username": "supervisor_auth", "password": "Test12345!"},
		)

		self.assertRedirects(response, reverse("dashboard:supervisor"))
		self.assertIn("_auth_user_id", self.client.session)

	def test_login_succeeds_if_user_already_has_active_work_session(self):
		start_work_session(self.assistant)

		response = self.client.post(
			reverse("accounts:login"),
			data={"username": "assistant_auth", "password": "Test12345!"},
		)

		self.assertRedirects(response, reverse("dashboard:assistant"))
		self.assertIn("_auth_user_id", self.client.session)
		self.assertEqual(WorkSession.objects.filter(user=self.assistant, is_active=True).count(), 1)

	def test_logout_closes_work_session_and_logs_out_django(self):
		start_work_session(self.assistant)
		self.client.force_login(self.assistant)

		response = self.client.post(reverse("accounts:logout"))

		self.assertRedirects(response, reverse("accounts:login"))
		self.assertNotIn("_auth_user_id", self.client.session)

		ended_session = WorkSession.objects.get(user=self.assistant)
		self.assertFalse(ended_session.is_active)
		self.assertIsNotNone(ended_session.logout_at)

		open_logs_count = WorkStatusLog.objects.filter(user=self.assistant, ended_at__isnull=True).count()
		self.assertEqual(open_logs_count, 0)
