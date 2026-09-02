__all__ = ["AstroDataLabConfig"]
from dataclasses import dataclass, field


@dataclass
class AstroDataLabConfig:
    """Configuration for Astro Data Lab API client.

    Attributes
    ----------
    remote_directory : str
        Where `upload_file` puts files when no explicit root is given. This
        is the shared folder the "Send to Data Lab" button has always used
        and is kept as the default so that path is unchanged.
    user_root_template : str
        Template for a single user's GOATS storage, formatted with
        ``username``. The per-user root the VOSpace storage backend writes
        under, and deliberately *not* `remote_directory`: one folder shared
        by every PI is the arrangement `datalab` mode exists to replace.
    """

    remote_directory: str = "vos://goats_data"
    user_root_template: str = "vos://users/{username}/goats"
    base_url: str = "https://datalab.noirlab.edu"
    token_header: str = "X-DL-AuthToken"
    upload_header: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "application/octet-stream"}
    )
    timeout: float = 10  # Seconds.
    password_header: str = "X-DL-Password"

    def user_root(self, username: str) -> str:
        """Return the VOSpace root for `username`.

        Parameters
        ----------
        username : str
            Astro Data Lab username.

        Returns
        -------
        str
            e.g. ``"vos://users/alice/goats"``.
        """
        return self.user_root_template.format(username=username)
