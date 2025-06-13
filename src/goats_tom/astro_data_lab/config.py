__all__ = ["AstroDataLabConfig"]
from dataclasses import dataclass, field


@dataclass
class AstroDataLabConfig:
    """Configuration for Astro Data Lab API client."""

    remote_directory: str = "vos://goats_data"
    base_url: str = "https://datalab.noirlab.edu"
    token_header: str = "X-DL-AuthToken"
    upload_header: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "application/octet-stream"}
    )
    timeout: float = 10  # Seconds.
    password_header: str = "X-DL-Password"
