"""Configuration for CLI."""

__all__ = ["Config", "config"]

from dataclasses import dataclass


@dataclass()
class Config:
    host: str = "localhost"
    redis_port: int = 6379
    django_port: int = 8000
    addrport_regex_pattern: str = r"^(?:(?P<host>[^:]+):)?(?P<port>[0-9]+)$"

    def __post_init__(self) -> None:
        """Creates the full address."""
        self.django_addrport = f"{self.host}:{self.django_port}"
        self.redis_addrport = f"{self.host}:{self.redis_port}"


config = Config()
