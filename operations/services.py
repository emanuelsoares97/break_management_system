from django.db import transaction
from django.utils import timezone

from common.exceptions import DomainError
from operations.models import WorkSession, WorkStatus, WorkStatusLog


def _calculate_duration_seconds(started_at, ended_at):
    return int((ended_at - started_at).total_seconds())


def _get_active_work_session(user):
    session = (
        WorkSession.objects.select_for_update()
        .filter(user=user, is_active=True)
        .order_by("-login_at")
        .first()
    )
    if session is None:
        raise DomainError("User does not have an active work session.")
    return session


def _get_open_status_log(user, session):
    status_log = (
        WorkStatusLog.objects.select_for_update()
        .filter(user=user, session=session, ended_at__isnull=True)
        .order_by("-started_at")
        .first()
    )
    if status_log is None:
        raise DomainError("User does not have an open work status log.")
    return status_log


def _close_status_log(status_log, ended_at):
    status_log.ended_at = ended_at
    status_log.duration_seconds = _calculate_duration_seconds(status_log.started_at, ended_at)
    status_log.full_clean()
    status_log.save()
    return status_log


@transaction.atomic
def start_work_session(user):
    now = timezone.now()
    has_active_session = WorkSession.objects.select_for_update().filter(user=user, is_active=True).exists()
    if has_active_session:
        raise DomainError("User already has an active work session.")

    session = WorkSession(user=user, login_at=now, is_active=True)
    session.full_clean()
    session.save()

    status_log = WorkStatusLog(
        user=user,
        session=session,
        status=WorkStatus.READY,
        started_at=now,
    )
    status_log.full_clean()
    status_log.save()

    return session


@transaction.atomic
def end_work_session(user):
    now = timezone.now()
    session = _get_active_work_session(user)
    status_log = _get_open_status_log(user=user, session=session)

    _close_status_log(status_log=status_log, ended_at=now)

    session.logout_at = now
    session.is_active = False
    session.full_clean()
    session.save()

    return session
