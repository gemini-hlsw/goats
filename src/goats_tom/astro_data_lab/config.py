__all__ = ["AstroDataLabConfig"]


class AstroDataLabConfig:
    """Configuration for Astro Data Lab API client."""

    remote_directory = "vos://goats_data"
    base_url = "https://datalab.noirlab.edu"
    token_header = "X-DL-AuthToken"
    upload_header = {"Content-Type": "application/octet-stream"}
    timeout = 60  # Seconds.
