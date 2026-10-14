import socket
import threading
import time
from unittest import mock

import pytest
import requests

from goats_tom.astroquery import Observations as GOA
from goats_tom.astroquery.conf import conf


@pytest.fixture
def stalling_server():
    """Serve the start of a download, then go silent without closing."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    release = threading.Event()

    def serve():
        conn, _ = server.accept()
        conn.recv(65536)
        conn.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/x-tar\r\n"
            b"Content-Length: 1000000\r\n\r\n" + b"x" * 1024
        )
        release.wait(10)
        conn.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.getsockname()[1]}/download"
    release.set()
    thread.join()
    server.close()


def test_get_files_passes_timeout(tmp_path):
    response = mock.MagicMock()
    response.iter_content.return_value = iter([b"No files to download."])
    with mock.patch.object(GOA, "_session") as session:
        session.get.return_value = response
        GOA.get_files(tmp_path, progid="GN-2024A-Q-1")

    assert session.get.call_args.kwargs["timeout"] == (
        conf.GOA_TIMEOUT,
        conf.GOA_READ_TIMEOUT,
    )


def test_get_files_does_not_hang_on_stalled_download(tmp_path, stalling_server):
    with (
        conf.set_temp("GOA_READ_TIMEOUT", 1),
        mock.patch.object(
            GOA.url_helper, "get_tar_file_url", return_value=stalling_server
        ),
    ):
        start = time.monotonic()
        with pytest.raises(requests.ConnectionError):
            GOA.get_files(tmp_path, progid="GN-2024A-Q-1")

    assert time.monotonic() - start < 5
