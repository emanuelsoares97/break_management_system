from django.db import transaction
from django.utils import timezone

from accounts.models import SupervisorTeam, UserRole
from breaks.models import PauseRequest, PauseRequestStatus
from common.exceptions import DomainError
from operations.models import WorkStatus, WorkStatusLog
from operations.services import _get_active_work_session


def _calculate_duration_seconds(started_at, ended_at):
    return int((ended_at - started_at).total_seconds())


def _get_user_profile(user):
    profile = getattr(user, "profile", None)
    if profile is None:
        raise DomainError("User does not have a profile.")
    return profile


def _user_can_manage_team(supervisor, team):
    supervisor_profile = _get_user_profile(supervisor)
    if supervisor_profile.role != UserRole.SUPERVISOR:
        return False
    return SupervisorTeam.objects.filter(supervisor_profile=supervisor_profile, team=team).exists()


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


@transaction.atomic
def request_pause(user, pause_type):
    session = _get_active_work_session(user)
    profile = _get_user_profile(user)

    if profile.team is None:
        raise DomainError("User does not have an assigned team.")
    if not pause_type.is_active:
        raise DomainError("Pause type is not active.")

    has_pending = PauseRequest.objects.select_for_update().filter(
        user=user,
        status=PauseRequestStatus.PENDING,
    ).exists()
    if has_pending:
        raise DomainError("User already has a pending pause request.")

    has_active_pause = PauseRequest.objects.select_for_update().filter(
        user=user,
        status=PauseRequestStatus.APPROVED,
        ended_at__isnull=True,
    ).exists()
    if has_active_pause:
        raise DomainError("User already has an active pause.")

    pause_request = PauseRequest(
        user=user,
        team=profile.team,
        session=session,
        pause_type=pause_type,
        status=PauseRequestStatus.PENDING,
        requested_at=timezone.now(),
    )
    pause_request.full_clean()
    pause_request.save()

    return pause_request


@transaction.atomic
def approve_pause(pause_request, supervisor):
    now = timezone.now()
    pause_request = PauseRequest.objects.select_for_update().select_related("user", "team").get(pk=pause_request.pk)

    if pause_request.status != PauseRequestStatus.PENDING:
        raise DomainError("Pause request is not pending.")
    if not _user_can_manage_team(supervisor, pause_request.team):
        raise DomainError("Supervisor is not allowed to manage this team.")

    session = _get_active_work_session(pause_request.user)
    open_status = _get_open_status_log(user=pause_request.user, session=session)
    if open_status.status != WorkStatus.READY:
        raise DomainError("Current user status must be ready to approve pause.")

    pause_request.status = PauseRequestStatus.APPROVED
    pause_request.approved_at = now
    pause_request.approved_by = supervisor
    pause_request.started_at = now
    pause_request.full_clean()
    pause_request.save()

    open_status.ended_at = now
    open_status.duration_seconds = _calculate_duration_seconds(open_status.started_at, now)
    open_status.full_clean()
    open_status.save()

    paused_status = WorkStatusLog(
        user=pause_request.user,
        session=session,
        status=WorkStatus.PAUSED,
        pause_request=pause_request,
        started_at=now,
    )
    paused_status.full_clean()
    paused_status.save()

    return pause_request


@transaction.atomic
def reject_pause(pause_request, supervisor, reason=None):
    pause_request = PauseRequest.objects.select_for_update().select_related("team").get(pk=pause_request.pk)

    if pause_request.status != PauseRequestStatus.PENDING:
        raise DomainError("Pause request is not pending.")
    if not _user_can_manage_team(supervisor, pause_request.team):
        raise DomainError("Supervisor is not allowed to manage this team.")

    pause_request.status = PauseRequestStatus.REJECTED
    pause_request.rejected_at = timezone.now()
    pause_request.rejected_by = supervisor
    pause_request.rejection_reason = reason or ""
    pause_request.full_clean()
    pause_request.save()

    return pause_request


@transaction.atomic
def finish_active_pause(user):
    now = timezone.now()
    session = _get_active_work_session(user)

    pause_request = (
        PauseRequest.objects.select_for_update()
        .select_related("pause_type")
        .filter(user=user, status=PauseRequestStatus.APPROVED, ended_at__isnull=True)
        .order_by("-started_at")
        .first()
    )
    if pause_request is None:
        raise DomainError("User does not have an active pause.")
    if pause_request.started_at is None:
        raise DomainError("Active pause request does not have a start time.")

    open_status = _get_open_status_log(user=user, session=session)
    if open_status.status != WorkStatus.PAUSED:
        raise DomainError("Current user status must be paused to finish pause.")
    if open_status.pause_request_id != pause_request.id:
        raise DomainError("Open paused status does not match the active pause request.")

    pause_duration_seconds = _calculate_duration_seconds(pause_request.started_at, now)
    pause_request.status = PauseRequestStatus.FINISHED
    pause_request.ended_at = now
    pause_request.duration_seconds = pause_duration_seconds
    pause_request.is_over_limit = pause_duration_seconds > (pause_request.pause_type.duration_minutes * 60)
    pause_request.full_clean()
    pause_request.save()

    open_status.ended_at = now
    open_status.duration_seconds = _calculate_duration_seconds(open_status.started_at, now)
    open_status.full_clean()
    open_status.save()

    ready_status = WorkStatusLog(
        user=user,
        session=session,
        status=WorkStatus.READY,
        started_at=now,
    )
    ready_status.full_clean()
    ready_status.save()

    return pause_request
