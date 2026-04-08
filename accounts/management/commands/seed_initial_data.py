from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import SupervisorTeam, UserProfile, UserRole
from breaks.models import PauseType
from teams.models import Team


class Command(BaseCommand):
    help = "Seed minimal base data for manual MVP validation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-superuser",
            action="store_true",
            help="Create superuser admin/admin if it does not exist.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding base data..."))

        teams = self._seed_teams()
        self._seed_pause_types()
        users = self._seed_users(teams)
        self._seed_supervisor_teams(users, teams)

        if options["create_superuser"]:
            self._seed_optional_superuser()

        self.stdout.write(self.style.SUCCESS("Seed completed successfully."))

    def _seed_teams(self):
        teams_spec = [
            "Technical Team",
            "Training Team",
            "Retention Team",
        ]

        teams = {}
        for team_name in teams_spec:
            team, created = Team.objects.get_or_create(
                name=team_name,
                defaults={"is_active": True},
            )
            teams[team_name] = team
            self._print_status("Team", team_name, created)

        return teams

    def _seed_pause_types(self):
        pause_types_spec = [
            {"name": "Pause 1", "code": "pause_1", "duration": 15},
            {"name": "Pause 2", "code": "pause_2", "duration": 15},
            {"name": "Lunch", "code": "lunch", "duration": 60},
            {"name": "Briefing", "code": "briefing", "duration": 10},
        ]

        for item in pause_types_spec:
            pause_type, created = PauseType.objects.get_or_create(
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "duration_minutes": item["duration"],
                    "requires_approval": True,
                    "is_active": True,
                },
            )

            if not created:
                updated = False
                if pause_type.name != item["name"]:
                    pause_type.name = item["name"]
                    updated = True
                if pause_type.duration_minutes != item["duration"]:
                    pause_type.duration_minutes = item["duration"]
                    updated = True
                if pause_type.requires_approval is not True:
                    pause_type.requires_approval = True
                    updated = True
                if pause_type.is_active is not True:
                    pause_type.is_active = True
                    updated = True
                if updated:
                    pause_type.full_clean()
                    pause_type.save()

            self._print_status("PauseType", item["code"], created)

    def _seed_users(self, teams):
        users_spec = [
            {
                "username": "supervisor1",
                "password": "Test12345!",
                "role": UserRole.SUPERVISOR,
                "team_name": "Technical Team",
            },
            {
                "username": "assistant1",
                "password": "Test12345!",
                "role": UserRole.ASSISTANT,
                "team_name": "Retention Team",
            },
            {
                "username": "assistant2",
                "password": "Test12345!",
                "role": UserRole.ASSISTANT,
                "team_name": "Technical Team",
            },
            {
                "username": "assistant3",
                "password": "Test12345!",
                "role": UserRole.ASSISTANT,
                "team_name": "Training Team",
            },
        ]

        users = {}
        for item in users_spec:
            user, created = User.objects.get_or_create(username=item["username"])
            user.set_password(item["password"])
            user.is_active = True
            user.save()

            profile, profile_created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "role": item["role"],
                    "team": teams[item["team_name"]],
                    "is_active": True,
                },
            )

            if not profile_created:
                profile.role = item["role"]
                profile.team = teams[item["team_name"]]
                profile.is_active = True
                profile.full_clean()
                profile.save()

            users[item["username"]] = user
            self._print_status("User", item["username"], created)
            self._print_status("UserProfile", item["username"], profile_created)

        return users

    def _seed_supervisor_teams(self, users, teams):
        supervisor_profile = users["supervisor1"].profile
        team_names = ["Technical Team", "Training Team", "Retention Team"]

        for team_name in team_names:
            assignment, created = SupervisorTeam.objects.get_or_create(
                supervisor_profile=supervisor_profile,
                team=teams[team_name],
            )
            self._print_status(
                "SupervisorTeam",
                f"{supervisor_profile.user.username} -> {assignment.team.name}",
                created,
            )

    def _seed_optional_superuser(self):
        username = "admin"
        password = "admin"
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        if not created:
            changed = False
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if not user.is_superuser:
                user.is_superuser = True
                changed = True
            if not user.is_active:
                user.is_active = True
                changed = True
            if changed:
                user.save()

        user.set_password(password)
        user.save()
        self._print_status("Superuser", username, created)

    def _print_status(self, label, identity, created):
        state = "created" if created else "already existed"
        self.stdout.write(f"- {label}: {identity} [{state}]")
