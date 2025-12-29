"""
This module defines immutable configuration values used by the GOATS command-line
interface.
"""

__all__ = ["config"]

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Immutable configuration for the GOATS CLI."""

    host: str = "localhost"
    """Hostname for services to bind to."""

    redis_port: int = 6379
    """Port for Redis server."""

    django_port: int = 8000
    """Port for Django server."""

    addrport_regex_pattern: str = r"^(?:(?P<host>[^:]+):)?(?P<port>[0-9]+)$"
    """Regex pattern for matching host:port strings."""

    recopy_exclude_normal: tuple[str, ...] = (
        "**",
        "!{{ project_name }}/settings/__init__.py",
        "!{{ project_name }}/settings/base.py",
        "!{{ project_name }}/settings/dynamic.py",
        "!{{ project_name }}/settings/environments/**",
    )
    """Files to exclude from recopy in 'normal' mode."""

    recopy_exclude_full: tuple[str, ...] = (
        "**",
        "!{{ project_name }}/settings/__init__.py",
        "!{{ project_name }}/settings/base.py",
        "!{{ project_name }}/settings/dynamic.py",
        "!{{ project_name }}/settings/environments/**",
        "!manage.py",
        "!{{ project_name }}/asgi.py",
        "!{{ project_name }}/wsgi.py",
        "!{{ project_name }}/urls.py",
        "!{{ project_name }}/__init__.py",
    )
    """Files to exclude from recopy in 'full' mode."""

    never_overwrite: tuple[str, ...] = (
        "{{ project_name }}/settings/local.py",
        "{{ project_name }}/settings/generated.py",
    )
    """Files we never overwrite in *any* recopy mode."""

    update_doc_url: str = "https://goats.readthedocs.io/en/stable/updating.html"
    """URL for update documentation."""

    su_username: str = "admin"
    """Default superuser username."""

    su_email: str = "admin@example.com"
    """Default superuser email."""

    @property
    def django_addrport(self) -> str:
        """Return Django host:port string.

        Returns
        -------
        str
            Django address in host:port format.

        """
        return f"{self.host}:{self.django_port}"

    @property
    def redis_addrport(self) -> str:
        """
        Return Redis host:port string.

        Returns
        -------
        str
            Redis address in host:port format.

        """
        return f"{self.host}:{self.redis_port}"


config = Config()
