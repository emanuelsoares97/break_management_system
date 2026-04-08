from django.contrib.auth.models import User
from django.test import TestCase

from common.exceptions import DomainError
from operations.models import WorkSession, WorkStatus, WorkStatusLog
from operations.services import end_work_session, start_work_session


class WorkSessionServicesTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username="ops_user",
			password="Test12345!",
		)

	def test_start_work_session_creates_session_and_ready_log(self):
		session = start_work_session(self.user)

		self.assertTrue(session.is_active)
		self.assertIsNone(session.logout_at)
		self.assertEqual(WorkSession.objects.filter(user=self.user, is_active=True).count(), 1)

		open_log = WorkStatusLog.objects.get(user=self.user, session=session, ended_at__isnull=True)
		self.assertEqual(open_log.status, WorkStatus.READY)
		self.assertIsNone(open_log.pause_request)

	def test_start_work_session_fails_if_active_session_exists(self):
		start_work_session(self.user)

		with self.assertRaises(DomainError):
			start_work_session(self.user)

	def test_end_work_session_closes_session_and_open_status_log(self):
		session = start_work_session(self.user)

		ended_session = end_work_session(self.user)

		self.assertEqual(ended_session.id, session.id)
		self.assertFalse(ended_session.is_active)
		self.assertIsNotNone(ended_session.logout_at)

		closed_log = WorkStatusLog.objects.get(user=self.user, session=session)
		self.assertIsNotNone(closed_log.ended_at)
		self.assertIsNotNone(closed_log.duration_seconds)

	def test_end_work_session_fails_if_no_active_session_exists(self):
		with self.assertRaises(DomainError):
			end_work_session(self.user)
