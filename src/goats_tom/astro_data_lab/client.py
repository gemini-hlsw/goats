__all__ = ["AstroDataLabClient"]

from pathlib import Path
from typing import Optional

import requests

from .config import AstroDataLabConfig


class AstroDataLabClient:
    """Client for interacting with the Astro Data Lab API.

    Parameters
    ----------
    username : str
        Astro Data Lab username.
    password : str
        Astro Data Lab password.
    token : str, optional
        Authentication token, by default `None`.
    config : AstroDataLabConfig, optional
        Custom configuration, by default `None`.
    """

    def __init__(
        self,
        username: str,
        password: str,
        token: Optional[str] = None,
        config: Optional[AstroDataLabConfig] = None,
    ) -> None:
        self.username = username
        self.password = password
        self.token: Optional[str] = token
        self.config = config or AstroDataLabConfig()
        self._session = requests.Session()

    def close(self) -> None:
        """Close the session."""
        self._session.close()

    def __enter__(self) -> "AstroDataLabClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def login(self) -> str:
        """Authenticate and obtain a token.

        Returns
        -------
        str
            Authentication token.
        """
        url = f"{self.config.base_url}/auth/login?username={self.username}"
        headers = {self.config.password_header: self.password}
        response = self._session.get(url, headers=headers, timeout=self.config.timeout)
        response.raise_for_status()
        self.token = response.text.strip()
        return self.token

    def is_logged_in(self) -> bool:
        """Check if the current token is valid.

        Returns
        -------
        bool
            `True` if token is valid, `False` otherwise.
        """
        if not self.token:
            return False
        url = f"{self.config.base_url}/auth/isValidToken?token={self.token}"
        headers = {self.config.token_header: self.token}
        response = self._session.get(url, headers=headers, timeout=self.config.timeout)
        response.raise_for_status()
        return response.text.strip() == "True"

    def mkdir(self) -> None:
        """Create the remote directory if it does not exist.

        Raises
        ------
        FileExistsError
            If the directory already exists.
        """
        url = f"{self.config.base_url}/storage/mkdir?dir={self.config.remote_directory}"
        headers = {self.config.token_header: self.token}
        response = self._session.get(url, headers=headers, timeout=self.config.timeout)
        if response.status_code == 409:
            raise FileExistsError(
                f"Directory already exists: {self.config.remote_directory}"
            )
        response.raise_for_status()

    def lsdir(self, path: Optional[str] = None) -> list:
        """List contents of the remote directory.

        Parameters
        ----------
        path : str, optional
            Path to list, by default the configured remote directory.

        Returns
        -------
        list
            List of file or directory names.

        Raises
        ------
        FileNotFoundError
            If the file or directory does not exist.
        """
        path = path or self.config.remote_directory
        url = f"{self.config.base_url}/storage/ls?name={path}&format=json"
        headers = {self.config.token_header: self.token}
        response = self._session.get(url, headers=headers, timeout=self.config.timeout)
        if response.status_code == 404:
            raise FileNotFoundError(f"Remote directory was not found: {path}.")
        response.raise_for_status()
        data = response.json()
        return data.get("contents", [])

    def check_file_exists(self, file_name: str) -> bool:
        """Check if a file exists in the remote directory.

        Parameters
        ----------
        file_name : str
            Name of the file.

        Returns
        -------
        bool
            `True` if the file exists, `False` otherwise.
        """
        path = f"{self.config.remote_directory}/{file_name}"
        try:
            return bool(self.lsdir(path))
        except FileNotFoundError:
            return False

    def delete_file(self, file_name: str) -> None:
        """Delete a file from the remote directory.

        Parameters
        ----------
        file_name : str
            Name of the file to delete.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        """
        url = (
            f"{self.config.base_url}/storage/rm"
            f"?file={self.config.remote_directory}/{file_name}"
        )
        headers = {self.config.token_header: self.token}
        response = self._session.get(url, headers=headers, timeout=self.config.timeout)
        if response.status_code == 404:
            raise FileNotFoundError(f"File does not exist: {file_name}.")
        response.raise_for_status()

    def _upload_file(self, uri: str, file_path: Path) -> None:
        """Upload a local file to the specified URI.

        Parameters
        ----------
        uri : str
            Upload URI.
        file_path : Path
            Path to the local file.
        """
        with file_path.open("rb") as f:
            response = self._session.put(
                uri,
                headers=self.config.upload_header,
                data=f,
                timeout=self.config.timeout,
            )
        response.raise_for_status()

    def _create_empty(self, file_name: str) -> str:
        """Reserve a file location in Astro Data Lab for upload.

        Parameters
        ----------
        file_name : str
            Name of the file.

        Returns
        -------
        str
            Upload URI.
        """
        url = (
            f"{self.config.base_url}/storage/put"
            f"?name={self.config.remote_directory}/{file_name}"
        )
        headers = {self.config.token_header: self.token}
        response = self._session.get(url, headers=headers, timeout=self.config.timeout)
        response.raise_for_status()
        return response.text.strip()

    def upload_file(self, file_path: Path | str, overwrite: bool = False) -> None:
        """Upload a file to Astro Data Lab.

        Parameters
        ----------
        file_path : Path | str
            Local file path.
        overwrite : bool, optional
            Whether to overwrite an existing file, by default `False`.

        Raises
        ------
        FileNotFoundError
            If the local file does not exist.
        FileExistsError
            If the remote file exists and overwrite is `False`.
        """
        file_path = Path(file_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Local file not found: {file_path}")
        file_name = file_path.name
        if self.check_file_exists(file_name):
            if overwrite:
                self.delete_file(file_name)
            else:
                raise FileExistsError(
                    f"File already exists: {file_name}. "
                    "Use 'overwrite=True' to replace."
                )
        uri = self._create_empty(file_name)
        self._upload_file(uri, file_path)
