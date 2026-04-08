from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.models import SupervisorTeam, UserProfile, UserRole
from breaks.models import PauseRequest, PauseRequestStatus, PauseType
from breaks.services import approve_pause, finish_active_pause, reject_pause, request_pause
from common.exceptions import DomainError
from operations.models import WorkStatus, WorkStatusLog
from operations.services import start_work_session
from teams.models import Team


class BreakServicesTests(TestCase):
	def setUp(self):
		self.team = Team.objects.create(name="Retention Team")
		self.other_team = Team.objects.create(name="Technical Team")

		self.assistant = User.objects.create_user(username="assistant_test", password="Test12345!")
		self.supervisor = User.objects.create_user(username="supervisor_test", password="Test12345!")

		self.assistant_profile = UserProfile.objects.create(
			user=self.assistant,
			role=UserRole.ASSISTANT,
			team=self.team,
		)
		self.supervisor_profile = UserProfile.objects.create(
			user=self.supervisor,
			role=UserRole.SUPERVISOR,
			team=self.other_team,
		)
		SupervisorTeam.objects.create(supervisor_profile=self.supervisor_profile, team=self.team)

		self.pause_type = PauseType.objects.create(
			name="Pause 1",
			code="pause_1",
			duration_minutes=15,
			requires_approval=True,
			is_active=True,
		)

	def _start_assistant_session(self):
		return start_work_session(self.assistant)

	def test_request_pause_creates_pending_request(self):
		session = self._start_assistant_session()

		pause_request = request_pause(self.assistant, self.pause_type)

		self.assertEqual(pause_request.session_id, session.id)
		self.assertEqual(pause_request.status, PauseRequestStatus.PENDING)
		self.assertEqual(pause_request.team_id, self.team.id)

	def test_request_pause_fails_without_active_session(self):
		with self.assertRaises(DomainError):
			request_pause(self.assistant, self.pause_type)

	def test_request_pause_fails_when_user_has_no_team(self):
		self._start_assistant_session()
		self.assistant_profile.team = None
		self.assistant_profile.save(update_fields=["team"])

		with self.assertRaises(DomainError):
			request_pause(self.assistant, self.pause_type)

	def test_request_pause_fails_if_pending_request_already_exists(self):
		self._start_assistant_session()
		request_pause(self.assistant, self.pause_type)

		with self.assertRaises(DomainError):
			request_pause(self.assistant, self.pause_type)

	def test_request_pause_fails_if_active_pause_already_exists(self):
		session = self._start_assistant_session()
		PauseRequest.objects.create(
			user=self.assistant,
			team=self.team,
			session=session,
			pause_type=self.pause_type,
			status=PauseRequestStatus.APPROVED,
			requested_at=timezone.now(),
			approved_at=timezone.now(),
			approved_by=self.supervisor,
			started_at=timezone.now(),
		)

		with self.assertRaises(DomainError):
			request_pause(self.assistant, self.pause_type)

	def test_approve_pause_approves_and_switches_status_logs(self):
		session = self._start_assistant_session()
		pause_request = request_pause(self.assistant, self.pause_type)

		approved = approve_pause(pause_request, self.supervisor)

		self.assertEqual(approved.status, PauseRequestStatus.APPROVED)
		self.assertEqual(approved.approved_by_id, self.supervisor.id)
		self.assertIsNotNone(approved.started_at)

		ready_log = WorkStatusLog.objects.get(user=self.assistant, session=session, status=WorkStatus.READY)
		self.assertIsNotNone(ready_log.ended_at)
		self.assertIsNotNone(ready_log.duration_seconds)

		paused_log = WorkStatusLog.objects.get(
			user=self.assistant,
			session=session,
			status=WorkStatus.PAUSED,
			ended_at__isnull=True,
		)
		self.assertEqual(paused_log.pause_request_id, approved.id)

	def test_approve_pause_fails_if_request_is_not_pending(self):
		self._start_assistant_session()
		pause_request = request_pause(self.assistant, self.pause_type)
		reject_pause(pause_request, self.supervisor, reason="no")

		with self.assertRaises(DomainError):
			approve_pause(pause_request, self.supervisor)

	def test_approve_pause_fails_if_supervisor_cannot_manage_team(self):
		unauthorized_supervisor = User.objects.create_user(
			username="supervisor_unauthorized",
			password="Test12345!",
		)
		UserProfile.objects.create(
			user=unauthorized_supervisor,
			role=UserRole.SUPERVISOR,
			team=self.other_team,
		)

		self._start_assistant_session()
		pause_request = request_pause(self.assistant, self.pause_type)

		with self.assertRaises(DomainError):
			approve_pause(pause_request, unauthorized_supervisor)

	def test_reject_pause_updates_status_and_reason(self):
		self._start_assistant_session()
		pause_request = request_pause(self.assistant, self.pause_type)

		rejected = reject_pause(pause_request, self.supervisor, reason="Queue busy")

		self.assertEqual(rejected.status, PauseRequestStatus.REJECTED)
		self.assertEqual(rejected.rejected_by_id, self.supervisor.id)
		self.assertEqual(rejected.rejection_reason, "Queue busy")
		self.assertIsNotNone(rejected.rejected_at)

	def test_finish_active_pause_finishes_pause_and_reopens_ready(self):
		session = self._start_assistant_session()
		pause_request = request_pause(self.assistant, self.pause_type)
		approve_pause(pause_request, self.supervisor)

		finished = finish_active_pause(self.assistant)

		self.assertEqual(finished.status, PauseRequestStatus.FINISHED)
		self.assertIsNotNone(finished.ended_at)
		self.assertIsNotNone(finished.duration_seconds)

		paused_log = WorkStatusLog.objects.get(
			user=self.assistant,
			session=session,
			status=WorkStatus.PAUSED,
			pause_request=finished,
		)
		self.assertIsNotNone(paused_log.ended_at)

		ready_logs_count = WorkStatusLog.objects.filter(
			user=self.assistant,
			session=session,
			status=WorkStatus.READY,
		).count()
		self.assertEqual(ready_logs_count, 2)

		new_open_ready = WorkStatusLog.objects.get(
			user=self.assistant,
			session=session,
			status=WorkStatus.READY,
			ended_at__isnull=True,
		)
		self.assertIsNone(new_open_ready.pause_request)

	def test_finish_active_pause_sets_over_limit_when_duration_exceeds_limit(self):
		session = self._start_assistant_session()
		pause_request = request_pause(self.assistant, self.pause_type)
		approved = approve_pause(pause_request, self.supervisor)

		self.pause_type.duration_minutes = 1
		self.pause_type.save(update_fields=["duration_minutes"])

		started_at = timezone.now() - timedelta(minutes=2)
		approved.started_at = started_at
		approved.save(update_fields=["started_at"])

		paused_log = WorkStatusLog.objects.get(
			user=self.assistant,
			session=session,
			status=WorkStatus.PAUSED,
			ended_at__isnull=True,
		)
		paused_log.started_at = started_at
		paused_log.save(update_fields=["started_at"])

		finished = finish_active_pause(self.assistant)

		self.assertTrue(finished.is_over_limit)
