import os
from typing import Optional

import requests


BASE_URL = "https://datalab.noirlab.edu"
TOKEN_HEADER = "X-DL-AuthToken"
TIMEOUT = 60  # seconds


class AstroDataLabClient:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.token: Optional[str] = None

    def login(self) -> str:
        url = f"{BASE_URL}/auth/login?username={self.username}"
        headers = {"X-DL-Password": self.password}
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        self.token = response.text.strip()
        return self.token

    def is_logged_in(self) -> bool:
        if not self.token:
            raise ValueError("No token available. Call login() first.")
        url = f"{BASE_URL}/auth/isValidToken?token={self.token}"
        headers = {TOKEN_HEADER: self.token}
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        return response.text.strip() == "True"

    def mkdir(self, path: str) -> bool:
        if not path.startswith("vos://"):
            raise ValueError("VOSPath must start with 'vos://'")
        url = f"{BASE_URL}/storage/mkdir?dir={path}"
        headers = {TOKEN_HEADER: self.token}
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        if response.status_code == 409:
            raise ValueError("Directory already exists")
        response.raise_for_status()
        return True

    def create_empty(self, path: str) -> str:
        if not path.startswith("vos://"):
            raise ValueError("VOSPath must start with 'vos://'")
        url = f"{BASE_URL}/storage/put?name={path}"
        headers = {TOKEN_HEADER: self.token}
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        return response.text.strip()

    def upload_file(self, upload_url: str, file_path: str) -> None:
        if not os.path.isfile(file_path):
            raise ValueError(f"File not found: {file_path}")
        with open(file_path, "rb") as f:
            response = requests.put(
                upload_url,
                headers={"Content-Type": "application/octet-stream"},
                data=f,
                timeout=TIMEOUT,
            )
        response.raise_for_status()
