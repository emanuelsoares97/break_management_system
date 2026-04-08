from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import SupervisorTeam, UserProfile, UserRole
from breaks.models import PauseRequest, PauseRequestStatus, PauseType
from operations.models import WorkSession, WorkStatus, WorkStatusLog
from operations.services import start_work_session
from teams.models import Team


class SupervisorDashboardPollingTests(TestCase):
	def setUp(self):
		self.team = Team.objects.create(name="Retention Team")
		self.other_team = Team.objects.create(name="Technical Team")

		self.supervisor = User.objects.create_user(username="sup_poll", password="Test12345!")
		self.supervisor_profile = UserProfile.objects.create(
			user=self.supervisor,
			role=UserRole.SUPERVISOR,
			team=self.team,
		)
		SupervisorTeam.objects.create(supervisor_profile=self.supervisor_profile, team=self.team)

		self.assistant = User.objects.create_user(username="assistant_poll", password="Test12345!")
		UserProfile.objects.create(
			user=self.assistant,
			role=UserRole.ASSISTANT,
			team=self.team,
		)

		self.other_assistant = User.objects.create_user(username="assistant_other", password="Test12345!")
		UserProfile.objects.create(
			user=self.other_assistant,
			role=UserRole.ASSISTANT,
			team=self.other_team,
		)

		self.pause_type = PauseType.objects.create(
			name="Pause 1",
			code="pause_1_poll",
			duration_minutes=15,
			requires_approval=True,
			is_active=True,
		)

	def test_poll_requires_login(self):
		response = self.client.get(reverse("dashboard:supervisor-poll"))
		self.assertEqual(response.status_code, 302)

	def test_poll_forbids_assistant(self):
		self.client.force_login(self.assistant)

		response = self.client.get(reverse("dashboard:supervisor-poll"))

		self.assertEqual(response.status_code, 403)

	def test_poll_returns_expected_payload_for_supervisor(self):
		session = start_work_session(self.assistant)
		PauseRequest.objects.create(
			user=self.assistant,
			team=self.team,
			session=session,
			pause_type=self.pause_type,
			status=PauseRequestStatus.PENDING,
		)

		start_work_session(self.other_assistant)

		self.client.force_login(self.supervisor)
		response = self.client.get(reverse("dashboard:supervisor-poll"))

		self.assertEqual(response.status_code, 200)
		payload = response.json()

		self.assertIn("stats", payload)
		self.assertIn("logged_in_assistants", payload)
		self.assertIn("pending_preview", payload)

		self.assertEqual(payload["stats"]["logged_in_assistants"], 1)
		self.assertEqual(payload["stats"]["pending_pause_requests"], 1)
		self.assertEqual(payload["stats"]["pauses_today"], 1)

		assistant_row = payload["logged_in_assistants"][0]
		self.assertEqual(assistant_row["username"], "assistant_poll")
		self.assertEqual(assistant_row["status"], WorkStatus.READY)
		self.assertEqual(assistant_row["status_label"], "Ready")

		pending_row = payload["pending_preview"][0]
		self.assertEqual(pending_row["username"], "assistant_poll")
		self.assertEqual(pending_row["team"], "Retention Team")

	def test_assistant_poll_requires_login(self):
		response = self.client.get(reverse("dashboard:assistant-poll"))
		self.assertEqual(response.status_code, 302)

	def test_assistant_poll_forbids_supervisor(self):
		self.client.force_login(self.supervisor)

		response = self.client.get(reverse("dashboard:assistant-poll"))

		self.assertEqual(response.status_code, 403)

	def test_assistant_poll_returns_active_pause_with_remaining_seconds(self):
		self.client.force_login(self.assistant)
		session = start_work_session(self.assistant)
		pause_request = PauseRequest.objects.create(
			user=self.assistant,
			team=self.team,
			session=session,
			pause_type=self.pause_type,
			status=PauseRequestStatus.APPROVED,
			started_at=session.login_at,
			approved_at=session.login_at,
			approved_by=self.supervisor,
		)
		WorkStatusLog.objects.filter(user=self.assistant, status=WorkStatus.READY, ended_at__isnull=True).update(ended_at=session.login_at)
		WorkStatusLog.objects.create(
			user=self.assistant,
			session=session,
			status=WorkStatus.PAUSED,
			pause_request=pause_request,
			started_at=session.login_at,
		)

		response = self.client.get(reverse("dashboard:assistant-poll"))
		self.assertEqual(response.status_code, 200)
		payload = response.json()

		self.assertIn("active_pause", payload)
		self.assertEqual(payload["current_status"]["status"], WorkStatus.PAUSED)
		self.assertIsNotNone(payload["active_pause"]["remaining_seconds"])


class MainFlowIntegrationTests(TestCase):
	def setUp(self):
		self.assistant_client = Client()
		self.supervisor_client = Client()

		self.team = Team.objects.create(name="Retention Team")

		self.supervisor = User.objects.create_user(username="supervisor_int", password="Test12345!")
		self.supervisor_profile = UserProfile.objects.create(
			user=self.supervisor,
			role=UserRole.SUPERVISOR,
			team=self.team,
		)
		SupervisorTeam.objects.create(supervisor_profile=self.supervisor_profile, team=self.team)

		self.assistant = User.objects.create_user(username="assistant_int", password="Test12345!")
		UserProfile.objects.create(
			user=self.assistant,
			role=UserRole.ASSISTANT,
			team=self.team,
		)

		self.pause_type = PauseType.objects.create(
			name="Pause Integration",
			code="pause_integration",
			duration_minutes=15,
			requires_approval=True,
			is_active=True,
		)

	def _login_assistant(self):
		response = self.assistant_client.post(
			reverse("accounts:login"),
			data={"username": "assistant_int", "password": "Test12345!"},
		)
		self.assertRedirects(response, reverse("dashboard:assistant"))

	def _login_supervisor(self):
		response = self.supervisor_client.post(
			reverse("accounts:login"),
			data={"username": "supervisor_int", "password": "Test12345!"},
		)
		self.assertRedirects(response, reverse("dashboard:supervisor"))

	def _request_pause(self):
		response = self.assistant_client.post(reverse("breaks:request", args=[self.pause_type.id]))
		self.assertRedirects(response, reverse("dashboard:assistant"))

		pause_request = PauseRequest.objects.get(user=self.assistant)
		self.assertEqual(pause_request.status, PauseRequestStatus.PENDING)
		return pause_request

	def _poll_payload(self):
		response = self.supervisor_client.get(reverse("dashboard:supervisor-poll"))
		self.assertEqual(response.status_code, 200)
		return response.json()

	def test_assistant_login_request_pause_and_poll_shows_pending(self):
		self._login_assistant()

		self.assertEqual(WorkSession.objects.filter(user=self.assistant, is_active=True).count(), 1)
		self._request_pause()

		self._login_supervisor()
		payload = self._poll_payload()

		self.assertEqual(payload["stats"]["logged_in_assistants"], 1)
		self.assertEqual(payload["stats"]["pending_pause_requests"], 1)
		self.assertEqual(payload["pending_preview"][0]["username"], "assistant_int")

	def test_supervisor_approves_pause_and_poll_reflects_paused(self):
		self._login_assistant()
		pause_request = self._request_pause()

		self._login_supervisor()
		approve_response = self.supervisor_client.post(reverse("breaks:approve", args=[pause_request.id]))
		self.assertRedirects(approve_response, reverse("breaks:pending"))

		pause_request.refresh_from_db()
		self.assertEqual(pause_request.status, PauseRequestStatus.APPROVED)

		ready_open_count = WorkStatusLog.objects.filter(
			user=self.assistant,
			status=WorkStatus.READY,
			ended_at__isnull=True,
		).count()
		self.assertEqual(ready_open_count, 0)

		paused_open_count = WorkStatusLog.objects.filter(
			user=self.assistant,
			status=WorkStatus.PAUSED,
			ended_at__isnull=True,
		).count()
		self.assertEqual(paused_open_count, 1)

		payload = self._poll_payload()
		self.assertEqual(payload["stats"]["pending_pause_requests"], 0)
		self.assertEqual(payload["stats"]["pauses_today"], 1)
		self.assertEqual(payload["logged_in_assistants"][0]["status"], WorkStatus.PAUSED)
		self.assertIsNotNone(payload["logged_in_assistants"][0]["pause_remaining_seconds"])

	def test_assistant_finishes_pause_and_poll_reflects_ready(self):
		self._login_assistant()
		pause_request = self._request_pause()

		self._login_supervisor()
		approve_response = self.supervisor_client.post(reverse("breaks:approve", args=[pause_request.id]))
		self.assertRedirects(approve_response, reverse("breaks:pending"))

		finish_response = self.assistant_client.post(reverse("breaks:finish-active"))
		self.assertRedirects(finish_response, reverse("dashboard:assistant"))

		pause_request.refresh_from_db()
		self.assertEqual(pause_request.status, PauseRequestStatus.FINISHED)

		paused_open_count = WorkStatusLog.objects.filter(
			user=self.assistant,
			status=WorkStatus.PAUSED,
			ended_at__isnull=True,
		).count()
		self.assertEqual(paused_open_count, 0)

		ready_open_count = WorkStatusLog.objects.filter(
			user=self.assistant,
			status=WorkStatus.READY,
			ended_at__isnull=True,
		).count()
		self.assertEqual(ready_open_count, 1)

		payload = self._poll_payload()
		self.assertEqual(payload["stats"]["pending_pause_requests"], 0)
		self.assertEqual(payload["stats"]["pauses_today"], 1)
		self.assertEqual(payload["logged_in_assistants"][0]["status"], WorkStatus.READY)

	def test_supervisor_rejects_pause_and_poll_clears_pending_preview(self):
		self._login_assistant()
		pause_request = self._request_pause()

		self._login_supervisor()
		reject_response = self.supervisor_client.post(
			reverse("breaks:reject", args=[pause_request.id]),
			data={"reason": "Queue busy"},
		)
		self.assertRedirects(reject_response, reverse("breaks:pending"))

		pause_request.refresh_from_db()
		self.assertEqual(pause_request.status, PauseRequestStatus.REJECTED)
		self.assertEqual(pause_request.rejected_by_id, self.supervisor.id)
		self.assertEqual(pause_request.rejection_reason, "Queue busy")

		payload = self._poll_payload()
		self.assertEqual(payload["stats"]["pending_pause_requests"], 0)
		self.assertEqual(len(payload["pending_preview"]), 0)

	def test_assistant_logout_removes_assistant_from_polling_list(self):
		self._login_assistant()
		self._login_supervisor()

		before_logout_payload = self._poll_payload()
		self.assertEqual(before_logout_payload["stats"]["logged_in_assistants"], 1)

		logout_response = self.assistant_client.post(reverse("accounts:logout"))
		self.assertRedirects(logout_response, reverse("accounts:login"))

		assistant_session = WorkSession.objects.get(user=self.assistant)
		self.assertFalse(assistant_session.is_active)

		open_logs = WorkStatusLog.objects.filter(user=self.assistant, ended_at__isnull=True).count()
		self.assertEqual(open_logs, 0)

		after_logout_payload = self._poll_payload()
		self.assertEqual(after_logout_payload["stats"]["logged_in_assistants"], 0)
		self.assertEqual(len(after_logout_payload["logged_in_assistants"]), 0)
