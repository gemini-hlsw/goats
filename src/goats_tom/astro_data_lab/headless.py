"""Headless job launching on Astro Data Lab's JupyterHub.

Server-deployment only. This module is never imported in ``local`` mode --
see `goats_tom.executors` for the lazy resolution that guarantees it.

Notes
-----
This talks to a *different service* than `AstroDataLabClient`. That client
uses the Data Lab science API (``/auth``, ``/storage``) with an
``X-DL-AuthToken`` header. Everything here goes to the JupyterHub in front
of the notebook servers, which uses ``Authorization: token <token>`` and
splits into two API surfaces that are easy to confuse:

- the **Hub** API at ``/hub/api/...``, which owns server spawning, and
- the **user server** API at ``/user/<user>/api/...``, which owns contents,
  sessions and kernels.

`ensure_server` is the only call against the Hub; everything else is
against the user server and 404s (or redirects to a login page) until the
Hub has finished spawning.

The single most important structural fact: **HTTP alone executes nothing.**
Staging a script with ``PUT /api/contents`` and creating a session with
``POST /api/sessions`` gets a kernel, but no code runs until an
``execute_request`` is written to the kernel's websocket. `launch` is
therefore the only method that needs a websocket, and the only one that
needs the optional ``websocket-client`` dependency.

The launched process outlives that websocket. The launcher cell calls
`subprocess.Popen` with ``start_new_session=True``, so the runner is
reparented out of the kernel's process group and survives kernel shutdown,
session deletion and Hub culling of the notebook server.

That detachment has a consequence worth stating plainly, because it shapes
the supervisor design: **there is no process API on the other side.** Once
disconnected, the runner cannot be inspected or signalled over HTTP. Status
comes from files the runner itself writes (`job_status`, `fetch_log`), and
`kill` has to open a *fresh* kernel purely to call ``os.kill`` on a
remembered PID. If the notebook server is gone, that PID is unreachable and
`kill` cannot work at all. Reaping a remote job is consequently best-effort
in exactly the way `_abort_running_consumer` is best-effort locally, and
for the same reason: the real guarantee has to live elsewhere. Here it is
the runner's own wall-clock deadline plus the `generation` fencing token
checked at ingest -- a runner that outlives its deadline exits on its own,
and one that outlives its generation has its writes rejected with a 409.
Never treat `kill` as the thing that stops a job.
"""

__all__ = [
    "DataLabHeadlessClient",
    "HeadlessConfig",
    "HeadlessError",
    "JobHandle",
    "JobState",
]

import json
import logging
import posixpath
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Where staged scripts, status files and logs live, relative to the user's
# notebook root.
#
# Deliberately NOT dot-prefixed. A hidden directory would keep this out of
# the PI's file browser, but jupyter-server's ContentsManager sets
# ``allow_hidden = False`` by default and rejects any write to a hidden path
# with a 400:
#
#     if not self.allow_hidden and is_hidden(os_path, self.root_dir):
#         raise web.HTTPError(400, f"Cannot create file or directory ...")
#
# So the staging directory has to be visible. That is arguably better for
# NOIRLab ops anyway -- a PI can see what GOATS put on their account.
JOB_ROOT = "goats_jobs"


@dataclass
class HeadlessConfig:
    """Connection settings for the Data Lab JupyterHub.

    Attributes
    ----------
    base_url : str
        Origin of the notebook host, e.g. ``https://gp13.datalab.noirlab.edu``.
    hub_url : str, optional
        Origin of the Hub, if it differs from `base_url`. Falls back to
        `base_url` when unset.
    timeout : float
        Per-request timeout in seconds.

    Notes
    -----
    Deliberately **not** `AstroDataLabConfig`. That class points at the
    science API (``datalab.noirlab.edu``, ``/auth`` and ``/storage``); the
    notebook servers live on a different host entirely. Sharing one
    `base_url` between them silently builds valid-looking URLs against the
    wrong service, which is a confusing failure to debug -- requests 404 or
    redirect to a login page rather than erroring usefully.

    The node name in the notebook host (``gp13``) is worth confirming with
    NOIRLab before this is wired to 300 accounts: if JupyterHub assigns
    users to nodes at spawn time rather than pinning them, the host cannot
    be a fixed setting and must be read from the Hub's user record after
    `ensure_server`.
    """

    base_url: str = "https://datalab.noirlab.edu"
    hub_url: Optional[str] = None
    timeout: float = 30.0
    job_root: str = JOB_ROOT
    kernel_name: str = "antares_py3.7"

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.hub_url = (self.hub_url or self.base_url).rstrip("/")
        self.job_root = self.job_root.strip("/")
        # Caught here rather than as a 400 from the far side, which arrives
        # as "Bad Request" with no hint that hiddenness is the problem.
        if any(part.startswith(".") for part in self.job_root.split("/")):
            raise ValueError(
                f"job_root {self.job_root!r} contains a hidden path component. "
                "jupyter-server sets allow_hidden=False by default and rejects "
                "writes to dot-prefixed paths with a 400."
            )


class HeadlessError(RuntimeError):
    """Raised when a headless operation fails unrecoverably."""


class JobState(str, Enum):
    """Lifecycle state of a remote job, as reported by its status file."""

    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class JobHandle:
    """Identifiers needed to inspect or kill a launched job.

    Attributes
    ----------
    username : str
        Data Lab account the job runs as.
    job_id : str
        GOATS-assigned job identifier; also the job's directory name.
    session_id : str
        Jupyter session id, retained so the session can be deleted.
    kernel_id : str
        Kernel that ran the launcher cell. Expected to be dead already.
    pid : int or None
        Remote PID of the detached runner, or `None` if the launcher cell
        did not report one.
    """

    username: str
    job_id: str
    session_id: str
    kernel_id: str
    pid: Optional[int] = None


# Runs inside the kernel. Kept deliberately dependency-free -- it must work
# on whatever Python the Data Lab image provides, and it is the one piece of
# code with no opportunity to fail loudly, since nothing is listening by the
# time it matters.
_LAUNCHER_CELL = '''
import json, os, shutil, subprocess, sys
# Remove finished jobs' directories.
#
# Done here, on a kernel that is being spawned anyway, rather than from a
# kernel of its own: every kernel stages a notebook and Jupyter drops an
# `.ipynb_checkpoints` beside it, so a cleanup-only kernel creates litter
# while clearing it. The contents API cannot do this at all -- it has no
# recursive delete and, with `allow_hidden` false, cannot even see the
# checkpoint directories that block a delete.
for _stale in {cleanup!r}:
    try:
        shutil.rmtree(os.path.join(os.path.dirname(os.getcwd()), _stale),
                      ignore_errors=True)
    except Exception:
        pass
# The kernel's working directory is the directory of the notebook that
# started the session, which is exactly where the runner was staged. Use it
# rather than expanduser("~"): the contents API serves paths relative to the
# server's root_dir, which is NOT guaranteed to be the home directory. If
# those differ, the runner writes status and logs somewhere the API cannot
# read, and the job looks permanently UNKNOWN while actually running fine --
# a silent failure that is very hard to diagnose from the GOATS side.
job_dir = os.getcwd()
print("GOATS_JOB_DIR=%s" % job_dir)
out = open(os.path.join(job_dir, "stdout.log"), "ab", buffering=0)
err = open(os.path.join(job_dir, "stderr.log"), "ab", buffering=0)
with open(os.path.join(job_dir, "status.json"), "w") as fh:
    json.dump({{"state": "pending", "pid": None}}, fh)
proc = subprocess.Popen(
    [sys.executable, "-u", os.path.join(job_dir, {script_name!r})] + {args!r},
    cwd=job_dir,
    stdout=out,
    stderr=err,
    stdin=subprocess.DEVNULL,
    # Detaches the runner from the kernel's process group so it survives
    # kernel shutdown and Hub culling of the notebook server.
    start_new_session=True,
    env={{**os.environ, **{env!r}}},
)
with open(os.path.join(job_dir, "status.json"), "w") as fh:
    json.dump({{"state": "running", "pid": proc.pid}}, fh)
print("GOATS_REMOTE_PID=%d" % proc.pid)
'''


class DataLabHeadlessClient:
    """Launch and inspect detached jobs on a Data Lab notebook server.

    Parameters
    ----------
    username : str
        Data Lab username whose server the job runs on.
    token : str
        JupyterHub API token for that user.
    config : `HeadlessConfig`, optional
        Connection settings. Defaults point at the science API host, which
        is almost certainly wrong -- pass the notebook host explicitly.

    Warnings
    --------
    `token` is a **JupyterHub** token, not the ``X-DL-AuthToken`` returned
    by `AstroDataLabClient.login`. Whether Data Lab issues one per account,
    or whether the science token is accepted by the Hub, is an open
    deployment question and must be confirmed with NOIRLab before Phase 1
    can run end to end.
    """

    def __init__(
        self,
        username: str,
        token: str,
        config: Optional[HeadlessConfig] = None,
    ) -> None:
        self.username = username
        self.token = token
        self.config = config or HeadlessConfig()
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"token {token}"})
        # Retries on connection-level failures, not just bad statuses.
        #
        # Polling a job means a GET every few seconds against a long-lived
        # session. JupyterHub sits behind a proxy that closes idle keep-alive
        # sockets, and urllib3 will happily hand out a pooled connection the
        # far end has already dropped -- surfacing as
        # `RemoteDisconnected: Remote end closed connection without response`
        # partway through a window. Retrying transparently reopens it.
        #
        # POST is deliberately absent from `allowed_methods` (urllib3's
        # default excludes it): retrying session creation could leave an
        # orphaned kernel holding memory on the PI's quota.
        retry = Retry(
            total=4,
            connect=4,
            read=2,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=4)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    def __enter__(self) -> "DataLabHeadlessClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # -- URL construction --------------------------------------------------

    @property
    def _hub(self) -> str:
        """Base URL of the Hub API (server spawning only)."""
        return f"{self.config.hub_url}/hub/api"

    @property
    def _user(self) -> str:
        """Base URL of this user's notebook server API."""
        return f"{self.config.base_url}/user/{self.username}/api"

    def _job_dir(self, job_id: str) -> str:
        """Return the contents-API path of a job's directory."""
        return posixpath.join(self.config.job_root, job_id)

    # -- Step 1: spawn -----------------------------------------------------

    def ensure_server(self, wait: float = 120.0, poll: float = 2.0) -> None:
        """Ensure this user's notebook server is running, spawning if needed.

        Parameters
        ----------
        wait : float, optional
            Seconds to wait for a spawning server to become ready.
        poll : float, optional
            Seconds between readiness checks.

        Raises
        ------
        HeadlessError
            If the server does not become ready within `wait`.

        Notes
        -----
        This is the Hub API call that was the missing piece: without it,
        every user-server request 404s or bounces to a login page, which
        looks like an auth failure rather than an unspawned server.

        A 201 means the server was ready immediately; 202 means the Hub
        accepted the spawn and is working on it; 400 means it was already
        running, which is a success for our purposes. Only 202 needs the
        poll loop.

        Cold spawns are slow enough (tens of seconds) that the handler
        editor should call this on *open* rather than on submit -- see the
        preview-warmth note in the handoff.
        """
        url = f"{self._hub}/users/{self.username}/server"
        response = self._session.post(url, timeout=self.config.timeout)

        if response.status_code in (201, 400):
            return
        if response.status_code != 202:
            raise HeadlessError(
                f"Could not spawn server for {self.username}: "
                f"{response.status_code} {response.text[:200]}"
            )

        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            time.sleep(poll)
            if self._server_ready():
                return
        raise HeadlessError(
            f"Server for {self.username} did not become ready within {wait:.0f}s."
        )

    def _server_ready(self) -> bool:
        """Return whether the Hub reports this user's server as ready."""
        try:
            response = self._session.get(
                f"{self._hub}/users/{self.username}", timeout=self.config.timeout
            )
            response.raise_for_status()
        except requests.RequestException:
            return False
        servers = response.json().get("servers") or {}
        return any(s.get("ready") for s in servers.values())

    # -- Step 2: stage -----------------------------------------------------

    def put_file(self, path: str, content: str, file_type: str = "file") -> None:
        """Write a text file to the user's notebook filesystem.

        Parameters
        ----------
        path : str
            Path relative to the notebook root.
        content : str
            File contents.
        file_type : str, optional
            Contents-API type, ``"file"`` or ``"notebook"``.
        """
        body: dict[str, Any] = {"type": file_type, "path": path}
        if file_type == "notebook":
            body["content"] = json.loads(content)
            body["format"] = "json"
        else:
            body["content"] = content
            body["format"] = "text"
        response = self._session.put(
            f"{self._user}/contents/{path}", json=body, timeout=self.config.timeout
        )
        response.raise_for_status()

    def _ensure_dir(self, path: str) -> None:
        """Create a directory on the notebook filesystem, ignoring conflicts.

        Notes
        -----
        The contents API has no ``mkdir -p``, so intermediate components are
        created one at a time. A 409 means it already exists.
        """
        parts = path.strip("/").split("/")
        for i in range(len(parts)):
            sub = "/".join(parts[: i + 1])
            response = self._session.put(
                f"{self._user}/contents/{sub}",
                json={"type": "directory"},
                timeout=self.config.timeout,
            )
            if response.status_code == 400 and "hidden" in response.text.lower():
                raise HeadlessError(
                    f"Data Lab refused to create {sub!r}: jupyter-server is "
                    "configured with allow_hidden=False and rejects "
                    "dot-prefixed paths. Set HeadlessConfig(job_root=...) to "
                    "a visible directory name."
                )
            if response.status_code not in (200, 201, 409):
                response.raise_for_status()

    # -- Steps 3-5: session, socket, detach --------------------------------

    def launch(
        self,
        script: str,
        args: Optional[list[str]] = None,
        script_name: str = "runner.py",
        extra_files: Optional[dict[str, str]] = None,
        env: Optional[dict[str, str]] = None,
        job_id: Optional[str] = None,
        exec_timeout: float = 60.0,
        cleanup_job_ids: Optional[list[str]] = None,
    ) -> JobHandle:
        """Stage a script and start it as a detached remote process.

        Parameters
        ----------
        script : str
            Full source of the runner to stage and execute.
        args : list of str, optional
            Command-line arguments passed to the runner.
        script_name : str, optional
            Filename to stage the script under.
        extra_files : dict, optional
            Additional ``{filename: content}`` written into the job
            directory before launch. The runner needs ``mydb.py`` (imported
            as a sibling so Data Lab needs no GOATS install), the PI's
            ``handler.py``, and ``job_spec.json``.
        env : dict, optional
            Extra environment variables for the runner. Carries the job
            token and subscription/generation identifiers.
        job_id : str, optional
            Job identifier; generated if omitted.
        cleanup_job_ids : list of str, optional
            Directories of earlier, finished jobs to remove before starting.
            Handled by the launcher cell so no extra kernel is needed.
        exec_timeout : float, optional
            Seconds to wait for the launcher cell to report a PID.

        Returns
        -------
        `JobHandle`
            Identifiers for the launched job.

        Raises
        ------
        HeadlessError
            If the websocket dependency is missing, or the launcher cell
            fails or reports no PID.

        Notes
        -----
        Assumes `ensure_server` has already succeeded.

        The websocket is closed and the session deleted before returning.
        Neither is needed once the runner is detached, and leaving them open
        would hold a kernel per PI -- the exact per-user resource pinning the
        offload exists to eliminate.
        """
        job_id = job_id or f"job-{uuid.uuid4().hex[:12]}"
        job_dir = self._job_dir(job_id)

        # Step 2: stage the runner where the launcher cell expects it.
        self._ensure_dir(job_dir)
        # Staged before the runner, so the runner cannot start against a
        # half-populated directory.
        for name, content in (extra_files or {}).items():
            self.put_file(posixpath.join(job_dir, name), content)
        self.put_file(posixpath.join(job_dir, script_name), script)

        # Steps 3-5: session, socket, detach.
        cell = _LAUNCHER_CELL.format(
            cleanup=[str(x) for x in (cleanup_job_ids or [])],

            job_id=job_id,
            script_name=script_name,
            args=list(args or []),
            env=dict(env or {}),
        )
        pid, error, session_id, kernel_id = self._run_cell(
            cell,
            timeout=exec_timeout,
            notebook_path=posixpath.join(job_dir, f"{job_id}.ipynb"),
        )
        if error:
            raise HeadlessError(f"Launcher cell failed: {error}")

        if pid is None:
            raise HeadlessError(
                f"Launcher cell for {job_id} reported no PID; job state unknown."
            )

        logger.info(
            "Launched remote job %s for %s (pid=%s, kernel=%s).",
            job_id,
            self.username,
            pid,
            kernel_id,
        )
        return JobHandle(
            username=self.username,
            job_id=job_id,
            session_id=session_id,
            kernel_id=kernel_id,
            pid=pid,
        )

    def _run_cell(
        self,
        code: str,
        timeout: float = 60.0,
        notebook_path: Optional[str] = None,
    ) -> tuple[Optional[int], Optional[str], str, str]:
        """Run one cell on a fresh kernel and tear it down.

        Parameters
        ----------
        code : str
            Source to execute.
        timeout : float, optional
            Seconds to wait for the kernel to go idle.
        notebook_path : str, optional
            Session path, for legibility in the Hub's session list.

        Returns
        -------
        tuple
            ``(pid, error, session_id, kernel_id)``; `pid` is parsed from a
            ``GOATS_REMOTE_PID=`` marker if the cell emits one.

        Raises
        ------
        HeadlessError
            If ``websocket-client`` is missing or the socket cannot open.

        Notes
        -----
        The session is always deleted, including on failure. Kernels are the
        expensive resource on a shared notebook server, and a leaked one per
        launch would reintroduce the per-PI memory cost the offload exists to
        remove.
        """
        try:
            import websocket  # noqa: PLC0415 -- optional, server mode only
        except ModuleNotFoundError as exc:
            raise HeadlessError(
                "websocket-client is required to run remote jobs. "
                "Install the server extra: pip install 'goats[server]'."
            ) from exc

        # A caller-supplied path belongs to something with its own lifetime
        # -- a job directory that is removed when the job is cleaned up. One
        # generated here belongs to nothing, so it is removed below once the
        # cell has run. Without that, every kill and every ad-hoc cell left a
        # `cell-*.ipynb` on the PI's account permanently.
        transient_notebook = notebook_path is None
        notebook_path = notebook_path or posixpath.join(
            self.config.job_root, f"cell-{uuid.uuid4().hex[:8]}.ipynb"
        )
        # Stage a real notebook whose single cell is the launcher. The
        # session names this path, and pointing it at a file that does not
        # exist is at best untidy. Writing it also leaves an auditable
        # artifact: a PI or NOIRLab ops can open the notebook and see
        # exactly what GOATS ran, or re-run it by hand to debug.
        self._ensure_dir(posixpath.dirname(notebook_path))
        self.put_file(notebook_path, self._notebook_with_cell(code), "notebook")

        response = self._session.post(
            f"{self._user}/sessions",
            json={
                "path": notebook_path,
                "type": "notebook",
                "kernel": {"name": self.config.kernel_name},
            },
            timeout=self.config.timeout,
        )
        if response.status_code >= 400 and self.config.kernel_name in response.text:
            raise HeadlessError(
                f"Kernel {self.config.kernel_name!r} is not available for "
                f"{self.username}. Available kernels: {self.list_kernelspecs()}"
            )
        response.raise_for_status()
        session = response.json()
        session_id = session["id"]
        kernel_id = session["kernel"]["id"]

        # The websocket is the only thing that actually executes code;
        # everything before this point merely arranged for it.
        # Derived from `_user` rather than rebuilt from `base_url`, so the
        # HTTP and websocket URLs cannot drift apart. They must address the
        # same user server; constructing them independently means a change
        # to one silently leaves the other pointing elsewhere.
        ws_url = (
            self._user.replace("https://", "wss://").replace("http://", "ws://")
            + f"/kernels/{kernel_id}/channels"
        )
        try:
            ws = websocket.create_connection(
                ws_url,
                header=[f"Authorization: token {self.token}"],
                timeout=timeout,
            )
        except Exception as exc:
            self._delete_session(session_id)
            raise HeadlessError(f"Could not open kernel websocket: {exc}") from exc

        try:
            msg_id = uuid.uuid4().hex
            ws.send(json.dumps(self._execute_request(msg_id, code)))
            pid, error = self._read_until_idle(ws, msg_id, timeout)
        finally:
            try:
                ws.close()
            except Exception:
                logger.debug("Ignoring error closing kernel websocket.", exc_info=True)
            self._delete_session(session_id)
            if transient_notebook:
                try:
                    self._session.delete(
                        f"{self._user}/contents/{notebook_path}",
                        timeout=self.config.timeout,
                    )
                except requests.RequestException:
                    logger.debug(
                        "Could not remove %s.", notebook_path, exc_info=True
                    )

        return pid, error, session_id, kernel_id

    def list_kernelspecs(self) -> list[str]:
        """Return the kernel names available on this user's server.

        Returns
        -------
        list of str
            Kernel names, empty if the listing could not be retrieved.

        Notes
        -----
        Used to turn an opaque session-creation failure into a message that
        names the kernels that do exist. Worth calling early: a missing
        kernel is a per-account provisioning problem, not a code problem,
        and it looks identical to an auth error until you see the list.
        """
        try:
            response = self._session.get(
                f"{self._user}/kernelspecs", timeout=self.config.timeout
            )
            response.raise_for_status()
        except requests.RequestException:
            return []
        return sorted((response.json().get("kernelspecs") or {}).keys())

    def _notebook_with_cell(self, code: str) -> str:
        """Build a minimal nbformat v4 notebook holding `code` as one cell.

        Parameters
        ----------
        code : str
            Source of the single code cell.

        Returns
        -------
        str
            JSON-encoded notebook.

        Notes
        -----
        Hand-built rather than via ``nbformat`` so this stays dependency-free
        on the GOATS side -- the notebook is a handful of keys and importing
        a library to emit them would add weight to the server extra for no
        benefit. `kernelspec` is recorded so the file opens against the right
        kernel if a human later runs it interactively.
        """
        return json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": code.splitlines(keepends=True),
                    }
                ],
                "metadata": {
                    "kernelspec": {
                        "name": self.config.kernel_name,
                        "display_name": self.config.kernel_name,
                        "language": "python",
                    }
                },
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        )

    @staticmethod
    def _execute_request(msg_id: str, code: str) -> dict[str, Any]:
        """Build a Jupyter v5.3 ``execute_request`` message."""
        return {
            "header": {
                "msg_id": msg_id,
                "username": "goats",
                "session": uuid.uuid4().hex,
                "date": datetime.now(timezone.utc).isoformat(),
                "msg_type": "execute_request",
                "version": "5.3",
            },
            "parent_header": {},
            "metadata": {},
            "content": {
                "code": code,
                "silent": False,
                "store_history": False,
                "user_expressions": {},
                "allow_stdin": False,
                "stop_on_error": True,
            },
            "channel": "shell",
        }

    def _read_until_idle(
        self, ws, msg_id: str, timeout: float
    ) -> tuple[Optional[int], Optional[str]]:
        """Read kernel messages until our request goes idle.

        Returns
        -------
        tuple
            ``(pid, error)``; `pid` from the launcher's stdout marker and
            `error` from any kernel-side traceback.

        Notes
        -----
        Filters on `parent_header.msg_id`: a kernel multiplexes replies to
        every client on the same socket, so unrelated traffic must not be
        mistaken for ours.
        """
        pid: Optional[int] = None
        error: Optional[str] = None
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            try:
                raw = ws.recv()
            except Exception as exc:
                return pid, f"websocket closed before completion: {exc}"
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue

            msg_type = msg.get("msg_type") or msg.get("header", {}).get("msg_type")
            content = msg.get("content", {})

            if msg_type == "stream":
                for line in content.get("text", "").splitlines():
                    if line.startswith("GOATS_REMOTE_PID="):
                        try:
                            pid = int(line.split("=", 1)[1])
                        except ValueError:
                            pass
            elif msg_type == "error":
                error = "\n".join(content.get("traceback", [])) or content.get(
                    "evalue", "unknown error"
                )
            elif msg_type == "status" and content.get("execution_state") == "idle":
                return pid, error

        return pid, error or "timed out waiting for launcher cell"

    def _delete_session(self, session_id: str) -> None:
        """Delete a Jupyter session, best-effort."""
        try:
            self._session.delete(
                f"{self._user}/sessions/{session_id}", timeout=self.config.timeout
            )
        except requests.RequestException:
            logger.warning("Could not delete session %s.", session_id, exc_info=True)

    # -- Step 6: status and logs ------------------------------------------

    def _read_contents(self, path: str) -> Optional[str]:
        """Read a text file via the contents API, or `None` if absent."""
        response = self._session.get(
            f"{self._user}/contents/{path}",
            params={"type": "file", "format": "text", "content": "1"},
            timeout=self.config.timeout,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json().get("content")

    def delete_job_dir(self, job_id: str) -> bool:
        """Delete a job's directory and everything beneath it.

        Parameters
        ----------
        job_id : str
            Job identifier.

        Returns
        -------
        bool
            Whether the directory is gone afterwards. Verified by re-reading
            the path rather than inferred from the delete response.

        Notes
        -----
        Call once the job's status and logs have been collected. The runner
        scrubs its own credentials and code, but the directory, notebook and
        logs remain on the PI's account until this runs.

        Done from a kernel with `shutil.rmtree`, not through the contents
        API. The API has no recursive delete, refuses to remove a non-empty
        directory, and -- with ``allow_hidden`` false, the default -- cannot
        even *see* hidden entries. So a `.ipynb_checkpoints` directory, which
        Jupyter creates beside every notebook it opens, blocks the delete
        while remaining invisible to any listing the API can produce. Walking
        the tree over HTTP therefore cannot work in general, however many
        requests it makes.

        A kernel sees the real filesystem, so one `rmtree` call replaces the
        whole walk. The cost is a kernel spawn per cleanup, which is
        acceptable: this runs once per window, against a job that has already
        finished, and the alternative is unbounded litter on the PI's own
        storage.

        Failure is not raised: an undeleted directory is untidy, not
        dangerous, and must not abort a supervisor cycle.
        """
        directory = self._job_dir(job_id)
        if not self._exists(directory):
            return True

        try:
            _, error, _, _ = self._run_cell(
                "import os, shutil\n"
                f"shutil.rmtree(os.path.join(os.getcwd(), {job_id!r}), "
                "ignore_errors=True)\n",
                timeout=60.0,
            )
            if error:
                logger.warning("Could not delete %s: %s", directory, error)
        except Exception:
            logger.warning("Could not delete %s.", directory, exc_info=True)
            return False
        return not self._exists(directory)

    def _exists(self, path: str) -> bool:
        """Whether `path` is still present on the notebook filesystem."""
        try:
            response = self._session.get(
                f"{self._user}/contents/{path}", timeout=self.config.timeout
            )
        except requests.RequestException:
            return True
        return response.status_code != 404

    def job_status(self, job_id: str) -> dict[str, Any]:
        """Read a job's status file.

        Parameters
        ----------
        job_id : str
            Job identifier.

        Returns
        -------
        dict
            Parsed status with at least ``state``; `JobState.UNKNOWN` if no
            status file exists yet or it is unparseable.

        Notes
        -----
        This reports what the runner last *wrote*, not whether its process
        is alive -- there is no process API once detached. A job that
        segfaults leaves ``running`` behind forever, so the supervisor must
        treat a stale `last_heartbeat` as failure rather than trusting
        `state`.
        """
        raw = self._read_contents(posixpath.join(self._job_dir(job_id), "status.json"))
        if raw is None:
            return {"state": JobState.UNKNOWN, "reason": "no status file"}
        try:
            status = json.loads(raw)
        except ValueError:
            return {"state": JobState.UNKNOWN, "reason": "unparseable status file"}
        status.setdefault("state", JobState.UNKNOWN)
        return status

    def fetch_log(self, job_id: str, stream: str = "stdout") -> str:
        """Return a job's captured log.

        Parameters
        ----------
        job_id : str
            Job identifier.
        stream : str, optional
            ``"stdout"`` or ``"stderr"``.

        Returns
        -------
        str
            Log contents, empty if the file does not exist yet.
        """
        return (
            self._read_contents(
                posixpath.join(self._job_dir(job_id), f"{stream}.log")
            )
            or ""
        )

    def tail_ndjson(self, path: str, offset: int = 0) -> tuple[list[dict], int]:
        """Read new NDJSON records from a staged file.

        Parameters
        ----------
        path : str
            Path relative to the notebook root.
        offset : int, optional
            Number of records already consumed.

        Returns
        -------
        tuple
            ``(records, new_offset)``. `new_offset` stops at the first line
            that does not parse, so a partially flushed final line is
            re-read on the next poll rather than skipped.

        Notes
        -----
        The runner appends to this file while it runs, so reads routinely
        land mid-write and see a truncated last line. Counting that line as
        consumed would advance the offset past a record that is about to
        become valid, silently dropping it -- which matters because this is
        the path that recovers loci when a POST to the ingest endpoint is
        lost. Stopping at the first bad line costs one re-read and loses
        nothing.
        """
        raw = self._read_contents(path)
        if raw is None:
            return [], offset
        lines = [line for line in raw.splitlines() if line.strip()]
        records = []
        consumed = offset
        for line in lines[offset:]:
            try:
                records.append(json.loads(line))
            except ValueError:
                break
            consumed += 1
        return records, consumed

    def kill(self, handle: JobHandle) -> bool:
        """Attempt to terminate a detached job.

        Parameters
        ----------
        handle : `JobHandle`
            Handle returned by `launch`.

        Returns
        -------
        bool
            Whether the signal was delivered. `False` is routine, not
            exceptional.

        Warnings
        --------
        Best-effort only, and structurally weaker than a local abort. There
        is no process API, so this spawns a *fresh* kernel solely to call
        ``os.kill``; if the notebook server has been culled the PID is
        unreachable and this always returns `False`. Correctness must not
        depend on it -- the runner's own deadline and the `generation`
        fencing token are what actually stop stale work.
        """
        if handle.pid is None:
            return False
        try:
            self.ensure_server(wait=30.0)
            _, error, _, _ = self._run_cell(
                "import os, signal\n"
                "try:\n"
                f"    os.kill({handle.pid}, signal.SIGTERM)\n"
                "except ProcessLookupError:\n"
                "    pass\n"
            )
            return error is None
        except Exception:
            logger.warning(
                "Could not kill remote job %s (pid=%s); relying on deadline "
                "and generation fencing instead.",
                handle.job_id,
                handle.pid,
                exc_info=True,
            )
            return False
