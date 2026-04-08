# Manual Test Checklist (MVP)

## Pre-Conditions

- [ ] Run migrations successfully
- [ ] Seed data created with `python manage.py seed_initial_data`
- [ ] Test users available (`supervisor1`, `assistant1`, `assistant2`, `assistant3`)

## Authentication

- [ ] Login with valid assistant credentials succeeds
- [ ] Login with valid supervisor credentials succeeds
- [ ] Login with invalid credentials shows error message
- [ ] Logout succeeds and redirects to login page

## Work Session Lifecycle

- [ ] After login, one active `WorkSession` is created
- [ ] After login, one open `WorkStatusLog` with status `ready` is created
- [ ] After logout, active `WorkSession` is closed (`is_active=False`, `logout_at` set)
- [ ] After logout, open `WorkStatusLog` is closed (`ended_at` and `duration_seconds` set)

## Assistant Dashboard

- [ ] Assistant can access assistant dashboard
- [ ] Assistant sees available pause types
- [ ] Assistant cannot access supervisor dashboard (forbidden)

## Supervisor Dashboard

- [ ] Supervisor can access supervisor dashboard
- [ ] Supervisor sees logged assistants from managed teams
- [ ] Supervisor cannot access assistant dashboard (forbidden)

## Pause Request Flow

- [ ] Assistant submits a pause request successfully
- [ ] New request appears in supervisor pending list
- [ ] Assistant cannot submit a second pending request
- [ ] Assistant cannot request pause without active work session

## Approve / Reject Flow

- [ ] Supervisor approves a pending request
- [ ] Approved request status becomes `approved`
- [ ] `ready` status log is closed after approval
- [ ] New `paused` status log is opened after approval
- [ ] Supervisor rejects a pending request with reason
- [ ] Rejected request status becomes `rejected`
- [ ] `rejected_by` and `rejection_reason` are persisted

## Finish Active Pause

- [ ] Assistant finishes active pause successfully
- [ ] Pause status becomes `finished`
- [ ] Open `paused` status log is closed
- [ ] New `ready` status log is opened
- [ ] `is_over_limit` is `False` when within allowed duration
- [ ] `is_over_limit` is `True` when duration exceeds pause type limit

## Basic Access Safety

- [ ] Unauthenticated access to dashboards redirects to login
- [ ] Logout endpoint only accepts POST
- [ ] Pause action endpoints only accept POST
