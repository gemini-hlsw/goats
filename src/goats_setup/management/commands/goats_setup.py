"""Django command to install GOATS."""

import os
import re
import sys
from pathlib import Path
from typing import Literal

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.utils import get_random_secret_key
from django.template.loader import get_template
from django.utils import timezone
from packaging import version
from tom_setup.management.commands.tom_setup import Command as TOMCommand

PYTHON_VERSION: str = "3.12"
REDIS_HOST: str = "localhost"
REDIS_PORT: int = 6379
REDIS_ADDRPORT: str = f"{REDIS_HOST}:{REDIS_PORT}"


class Command(TOMCommand):
    """Setup wizard for GOATS.

    This class extends TOMCommand to provide a setup wizard for new GOATS
    projects.
    """

    help = "🐐 GOATS setup wizard."

    def welcome_banner(self, ci: bool = False) -> None:
        """Displays a welcome banner."""
        if ci:
            self.stdout.write("🐐 Running GOATS for CI, skipping prompts.")
            return

        welcome_text = (
            "🐐 Welcome to the GOATS setup wizard. This will assist you with your "
            "new GOATS project.\n"
        )
        prompt = "Proceed with GOATS setup? [y/N] "
        self.stdout.write(self.style.MIGRATE_HEADING(welcome_text))

        # Reusing the prompt logic from the original class
        while True:
            response = input(prompt).lower()
            if not response or response == "n":
                self.stdout.write()
                self.exit(self.style.ERROR("Aborting installation."), return_code=1)
            elif response == "y":
                break
            else:
                self.stdout.write("Invalid response. Please try again.")

    def exit(self, msg: str, return_code: int = 0) -> None:
        """Exit the script.

        Parameters
        ----------
        msg : `str`
            The exit message to display.
        return_code : `int`, optional
            The exit code, default is 0.

        """
        self.stdout.write(f"🐐 {msg}")
        sys.exit(return_code)

    def add_arguments(self, parser):
        """Add custom command arguments."""
        super().add_arguments(parser)
        parser.add_argument(
            "--media-dir",
            type=str,
            help="Path where the data directory will be created.",
        )
        # Combine Redis host and port into a single argument.
        parser.add_argument(
            "--redis-addrport",
            default=REDIS_ADDRPORT,
            type=str,
            help=(
                "Specify the Redis server IP address and port number. "
                "Examples: '6379', 'localhost:6379', '192.168.1.5:6379'. "
                "Providing only a port number (e.g., '6379') binds to localhost."
            ),
        )
        # Argument to be used for CI.
        parser.add_argument(
            "--ci",
            action="store_true",
            default=False,
            help="Run install in non-interactive CI mode (no prompts).",
        )

    def check_python(self) -> None:
        """Checks the Python version, exits if not compatible."""
        self.status("  Checking Python version... ")
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        if version.parse(current_version) < version.parse(PYTHON_VERSION):
            self.exit(
                self.style.ERROR(
                    f"Incompatible Python version found. Please install Python >= "
                    f"{PYTHON_VERSION}"
                ),
                return_code=1,
            )
        self.ok()

    def complete(self) -> None:
        """Exits with a 0 return code."""
        sys.exit()

    def generate_file(self, file_type: Literal["settings", "urls", "asgi"]) -> None:
        """Generates Django configuration files based on the specified file type.

        Parameters
        ----------
        file_type : `Literal["settings", "urls", "asgi"]`
            The type of file to generate.

        """
        self.status(f"  Generating {file_type}.py... ")
        template_name = f"goats_setup/{file_type}.tmpl"
        template = get_template(template_name)
        rendered = template.render(self.context)

        file_location = settings.BASE_DIR / settings.BASE_DIR.name / f"{file_type}.py"
        if not file_location.exists():
            msg = (
                f"Could not determine {file_type}.py location. Writing {file_type}.py "
                f"out to {file_location}. Please copy file to the proper location "
                "after script finishes."
            )
            self.stdout.write(self.style.WARNING(msg))

        with open(file_location, "w+") as file:
            file.write(rendered)

        self.ok()

    def generate_secret_key(self) -> None:
        """Generates a new secret key."""
        self.status("  Generating secret key... ")
        self.context["SECRET_KEY"] = get_random_secret_key()
        self.ok()

    def handle(self, *args, **options) -> None:
        """Handles the setup process."""
        ci = options.get("ci", False)
        self.context["CREATE_DATE"] = timezone.now()
        self.context["PROJECT_NAME"] = settings.BASE_DIR.name
        self.context["HINTS_ENABLED"] = False
        self.welcome_banner(ci=ci)
        self.stdout.write(self.style.MIGRATE_HEADING("Initial setup:"))
        self.check_python()
        self.setup_redis(redis_addrport=options.get("redis_addrport"))
        self.create_project_dirs(media_dir=options.get("media_dir"))
        self.generate_secret_key()
        self.get_target_type()
        # self.get_hint_preference()
        self.stdout.write(self.style.MIGRATE_HEADING("Copying templates:"))
        self.generate_file("settings")
        self.generate_file("urls")
        self.generate_file("asgi")
        self.run_migrations()
        self.create_pi(ci=ci)
        self.create_public_group()
        self.complete()

    def setup_redis(self, redis_addrport: str | None = None) -> None:
        """Handles the setup Redis process."""
        self.status("  Setting up Redis...")
        if redis_addrport is None:
            redis_addrport = REDIS_ADDRPORT

        # Regex pattern to match host and optionally a port.
        pattern = re.compile(r"^(?:(?P<host>[^:]+):)?(?P<port>[0-9]+)$")
        match = pattern.match(redis_addrport)

        if not match:
            self.exit(
                self.style.ERROR(
                    f"Invalid format for --redis-addrport: '{redis_addrport}'",
                ),
                return_code=1,
            )

        # Extract host and port from the regex match groups.
        self.context["REDIS_HOST"] = match.group("host") or REDIS_HOST
        self.context["REDIS_PORT"] = int(match.group("port"))
        self.ok()

    def run_migrations(self) -> None:
        """Runs the initial database migrations."""
        self.status("  Running initial migrations... ")
        call_command("migrate", interactive=False, verbosity=0)
        self.ok()

    def create_project_dirs(self, media_dir) -> None:
        """Creates necessary project directories."""
        self.status("  Creating project directories... ")

        # Determine the base directory for the 'data' directory
        if media_dir:
            data_dir = Path(media_dir).resolve()
        else:
            data_dir = settings.BASE_DIR / "data"

        # Create a list of directories to be created
        directories = ["templates", "static", "tmp"]
        data_dir.mkdir(parents=True, exist_ok=True)
        self.context["MEDIA_ROOT"] = data_dir

        for dir_name in directories:
            dir_path = settings.BASE_DIR / dir_name
            dir_path.mkdir(exist_ok=True)

        # Create a ".keep" file in the "static" directory
        (settings.BASE_DIR / "static" / ".keep").touch(exist_ok=True)

        self.ok()

    def get_target_type(self) -> None:
        """Gets the target type for the project."""
        self.context["TARGET_TYPE"] = "SIDEREAL"

    def create_pi(self, ci: bool = False) -> None:
        """Creates a Principal Investigator (PI) superuser."""
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "Principal Investigator (PI) and public user creation:",
            )
        )
        if ci:
            password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
            if not password:
                self.stdout.write(
                    self.style.WARNING(
                        "🐐 DJANGO_SUPERUSER_PASSWORD is not set; the superuser will "
                        "not be able to log in until a password is manually set."
                    )
                )

            call_command(
                "createsuperuser",
                verbosity=0,
                username="goats",
                email="goats@goats.com",
                interactive=False,
            )
        else:
            call_command(
                "createsuperuser",
                verbosity=0,
            )
        self.status("  PI Superuser created... ")
        self.ok()

    def create_public_group(self) -> None:
        """Creates and configures the "Public" group."""
        self.status("  Setting up Public group... ")
        group = Group.objects.create(name="Public")
        group.user_set.add(*User.objects.all())
        group.save()
        self.ok()
