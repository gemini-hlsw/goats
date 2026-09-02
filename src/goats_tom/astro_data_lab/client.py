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
    root : str, optional
        VOSpace directory this client reads and writes under. Defaults to
        the shared `AstroDataLabConfig.remote_directory`, which is what the
        "Send to Data Lab" button has always used. The storage backend
        passes the caller's own `AstroDataLabConfig.user_root` instead.
    """

    def __init__(
        self,
        username: str,
        password: str,
        token: Optional[str] = None,
        config: Optional[AstroDataLabConfig] = None,
        root: Optional[str] = None,
    ) -> None:
        self.username = username
        self.password = password
        self.token: Optional[str] = token
        self.config = config or AstroDataLabConfig()
        self.root = root or self.config.remote_directory
        self._session = requests.Session()

    def _headers(self) -> dict:
        """Return the auth header for a storage request."""
        return {self.config.token_header: self.token}

    def remote_uri(self, relative_path: str = "") -> str:
        """Return the full ``vos://`` URI for `relative_path` under `root`.

        Parameters
        ----------
        relative_path : str, optional
            Path relative to this client's root. Empty means the root
            itself.

        Returns
        -------
        str
            e.g. ``"vos://users/alice/goats/obs/target/file.fits"``.

        Notes
        -----
        Leading and trailing separators are stripped so that callers can be
        careless with them, which matters because Django hands storage
        backends names assembled by several different code paths.
        """
        relative_path = str(relative_path).strip("/")
        return f"{self.root}/{relative_path}" if relative_path else self.root

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

    def makedirs(self, relative_path: str = "") -> None:
        """Create `relative_path` under `root`, parents included.

        Parameters
        ----------
        relative_path : str, optional
            Directory relative to the root. Empty creates the root itself.

        Notes
        -----
        The ``/storage/mkdir`` endpoint does not create intermediate
        directories, so each level is requested in turn and a 409 is
        treated as success. Django storage backends are expected to create
        whatever directories a name implies, silently -- `FileSystemStorage`
        does, and code written against it does not create directories first.

        Failures other than "already exists" are swallowed at intermediate
        levels only. The write that follows is what reports a real problem,
        with a message about the file the caller actually asked for rather
        than about a directory they never mentioned.
        """
        parts = [p for p in str(relative_path).strip("/").split("/") if p]
        walked = ""
        for part in [""] + parts:
            walked = f"{walked}/{part}".strip("/") if part else ""
            url = (
                f"{self.config.base_url}/storage/mkdir"
                f"?dir={self.remote_uri(walked)}"
            )
            response = self._session.get(
                url, headers=self._headers(), timeout=self.config.timeout
            )
            if response.status_code == 409:
                continue
            response.raise_for_status()

    def exists(self, relative_path: str) -> bool:
        """Whether a file or directory exists at `relative_path`.

        Parameters
        ----------
        relative_path : str
            Path relative to the root.

        Returns
        -------
        bool
        """
        url = (
            f"{self.config.base_url}/storage/ls"
            f"?name={self.remote_uri(relative_path)}&format=json"
        )
        response = self._session.get(
            url, headers=self._headers(), timeout=self.config.timeout
        )
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return bool(response.json().get("contents", []))

    def delete(self, relative_path: str) -> None:
        """Delete the file at `relative_path`.

        Parameters
        ----------
        relative_path : str
            Path relative to the root.

        Notes
        -----
        A missing file is **not** an error. Django's `Storage.delete`
        contract is that the file is gone afterwards, and `FileSystemStorage`
        ignores `FileNotFoundError` for the same reason: a delete racing
        another delete should not raise.
        """
        url = (
            f"{self.config.base_url}/storage/rm"
            f"?file={self.remote_uri(relative_path)}"
        )
        response = self._session.get(
            url, headers=self._headers(), timeout=self.config.timeout
        )
        if response.status_code == 404:
            return
        response.raise_for_status()

    def read(self, relative_path: str) -> bytes:
        """Return the bytes of the file at `relative_path`.

        Parameters
        ----------
        relative_path : str
            Path relative to the root.

        Returns
        -------
        bytes

        Raises
        ------
        FileNotFoundError
            If no such file exists.

        Notes
        -----
        The client had upload, delete and list but no read, so nothing could
        get a file back out. `local_path` in `goats_tom.storage` is the main
        caller: every astrodata header read and every jdaviz view goes
        through here once the backend is remote.

        Reads whole. FITS files are large and streaming would be better, but
        ``/storage/get`` returns a one-shot URL and the callers all need a
        complete local file anyway -- `astrodata.open` seeks.
        """
        url = (
            f"{self.config.base_url}/storage/get"
            f"?name={self.remote_uri(relative_path)}"
        )
        response = self._session.get(
            url, headers=self._headers(), timeout=self.config.timeout
        )
        if response.status_code == 404:
            raise FileNotFoundError(f"File does not exist: {relative_path}.")
        response.raise_for_status()

        download_url = response.text.strip()
        download = self._session.get(download_url, timeout=self.config.timeout)
        download.raise_for_status()
        return download.content

    def write(self, relative_path: str, data) -> None:
        """Write `data` to `relative_path`, creating parents as needed.

        Parameters
        ----------
        relative_path : str
            Path relative to the root.
        data : bytes or file-like
            The content to store.

        Notes
        -----
        Overwrites. Django resolves name collisions *before* calling
        ``_save`` -- `get_available_name` appends a suffix -- so a backend
        that refused to overwrite would break that contract and fail writes
        Django believed it had already made safe.
        """
        parent = "/".join(str(relative_path).strip("/").split("/")[:-1])
        self.makedirs(parent)

        url = (
            f"{self.config.base_url}/storage/put"
            f"?name={self.remote_uri(relative_path)}"
        )
        response = self._session.get(
            url, headers=self._headers(), timeout=self.config.timeout
        )
        response.raise_for_status()
        upload_uri = response.text.strip()

        put = self._session.put(
            upload_uri,
            headers=self.config.upload_header,
            data=data,
            timeout=self.config.timeout,
        )
        put.raise_for_status()

    def listdir(self, relative_path: str = "") -> list[str]:
        """Return the names directly under `relative_path`.

        Parameters
        ----------
        relative_path : str, optional
            Directory relative to the root.

        Returns
        -------
        list of str
            Entry names, not full paths. Empty when the directory does not
            exist, matching `exists` rather than raising.
        """
        url = (
            f"{self.config.base_url}/storage/ls"
            f"?name={self.remote_uri(relative_path)}&format=json"
        )
        response = self._session.get(
            url, headers=self._headers(), timeout=self.config.timeout
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return [
            entry.get("name", entry) if isinstance(entry, dict) else entry
            for entry in response.json().get("contents", [])
        ]
