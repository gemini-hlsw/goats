#!/usr/bin/env python3
"""GOATS download runner — fetches one observation from GOA into VOSpace.

Staged onto a PI's Data Lab account and started detached by
`goats_tom.astro_data_lab.headless`. Runs as that PI, under their quota, and
writes into their own VOSpace.

**No GOATS imports.** Nothing here needs the ``goats_tom`` package installed
on Data Lab. Only the standard library and ``requests``, which the Data Lab
kernels already have.

Why this runs here at all
-------------------------
The GOA download is the one facility path that cannot be moved by swapping a
storage backend. LCO, SOAR, LT and BLANCO fetch bytes into memory and hand
them to ``dp.data.save(...)``, so a remote backend serves them unchanged.
GOA ships **tarballs**: the response has to be untarred, each member
decompressed, and the result written somewhere. Doing that on the GOATS host
puts proprietary data on the control-plane disk, which is the thing
``datalab`` mode exists to prevent.

Streamed, not staged
--------------------
The tarball is never written down. The response is read as a stream, the tar
is walked sequentially (``mode="r|*"``, which never seeks), and each member
is decompressed and uploaded as it emerges. One file is in flight at a time,
so a 40 GB program costs one file of disk rather than 40 GB of it.

`BUFFER_BEFORE_UPLOAD` is the one thing here that could not be settled
without a live account -- see its comment.

Authentication
--------------
A **cookie**, never a password. The VM logs into GOA as it always has and
passes only the ``gemini_archive_session`` value, which is what actually
authorizes a download. Gemini's own API documentation recommends exactly
this for scripts. The PI's archive password never leaves the VM.

What the VM does afterwards
---------------------------
Reads the headers itself, through the storage seam, with the same astrodata
code it uses today. This runner reports filenames and sizes and nothing
about content, so there is nothing new to trust: a runner that lied about a
header would otherwise write a false `DataProductMetadata` row that no later
check would catch.
"""

import argparse
import bz2
import json
import os
import posixpath
import sys
import tarfile
import time
import traceback

import requests

# Seconds between progress writes to `status.json`.
#
# The supervisor derives liveness from this file changing, so a long download
# that reports nothing gets reaped as lost while working perfectly. Also what
# makes a progress bar possible at all: without it the file changes only at
# start and end, and a PI watching a 40 GB program sees nothing for an hour.
PROGRESS_SECONDS = 5.0

# Read size for streaming the GOA response and decompressing members.
CHUNK_BYTES = 1024 * 1024

# Whether each member is buffered to a temporary file before upload.
#
# **Open question, and the default is the safe answer.** A fully streamed
# upload requires the Data Lab `/storage/put` endpoint to accept a chunked
# request body; if it insists on `Content-Length`, it cannot, because a
# member's decompressed size is not known until it has been decompressed.
#
# Buffering costs one file of local disk at a time -- bounded, brief, and
# still nothing like staging the whole tarball. Set this False once a live
# account confirms chunked uploads are accepted, and `_upload` streams
# straight from the decompressor with no temporary file at all.
BUFFER_BEFORE_UPLOAD = True

# Files removed from the job directory as soon as they are no longer needed.
#
# `job_spec.json` holds the PI's Data Lab token and their GOA session cookie.
# Anyone who reads that cookie can access their archive account. It is
# scrubbed the moment it has been loaded into memory.
#
# `status.json` and the logs are deliberately kept: they are the only channel
# by which the VM learns what happened.
SECRET_FILES = ("job_spec.json",)
CODE_FILES = ("download_runner.py",)


def write_status(job_dir, state, **extra):
    """Write `status.json` atomically.

    Notes
    -----
    Via a temporary file and `os.replace`, because the VM polls this through
    the contents API and would otherwise read half a file. This is the only
    channel by which a detached job reports anything, so a torn read looks
    identical to a crash.
    """
    path = os.path.join(job_dir, "status.json")
    tmp = path + ".tmp"
    payload = {"state": state, "pid": os.getpid(), "ts": time.time()}
    payload.update(extra)
    with open(tmp, "w") as fh:
        json.dump(payload, fh)
    os.replace(tmp, path)


def log_event(job_dir, **fields):
    """Append one NDJSON record to the job's log.

    Notes
    -----
    One JSON object per line, appended and flushed immediately, so the VM can
    tail it with `tail_ndjson` while the job runs. Flushing matters: buffered
    output would arrive in blocks and a PI would watch nothing happen for
    minutes at a time.
    """
    fields["ts"] = time.time()
    with open(os.path.join(job_dir, "events.ndjson"), "a") as fh:
        fh.write(json.dumps(fields) + "\n")
        fh.flush()


def scrub(job_dir, names):
    """Delete `names` from the job directory, ignoring what is not there."""
    for name in names:
        try:
            os.remove(os.path.join(job_dir, name))
        except OSError:
            pass


class VOSpace:
    """Minimal Data Lab storage client, sufficient for uploading.

    Notes
    -----
    Deliberately not GOATS's `AstroDataLabClient`. That class lives in the
    ``goats_tom`` package, which is not installed on Data Lab, and staging it
    would drag in its imports. This is the two calls this runner needs.
    """

    def __init__(self, base_url, token, root, timeout=60.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.root = root.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def _headers(self):
        return {"X-DL-AuthToken": self.token}

    def uri(self, relative_path):
        """Full ``vos://`` URI for a path under the root."""
        relative_path = str(relative_path).strip("/")
        return f"{self.root}/{relative_path}" if relative_path else self.root

    def makedirs(self, relative_path):
        """Create `relative_path` and its parents.

        Notes
        -----
        ``/storage/mkdir`` does not create intermediate directories, so each
        level is requested in turn and a 409 means it already exists.
        """
        parts = [p for p in str(relative_path).strip("/").split("/") if p]
        walked = ""
        for part in parts:
            walked = f"{walked}/{part}".strip("/")
            response = self._session.get(
                f"{self.base_url}/storage/mkdir?dir={self.uri(walked)}",
                headers=self._headers(),
                timeout=self.timeout,
            )
            if response.status_code == 409:
                continue
            response.raise_for_status()

    def put(self, relative_path, data):
        """Upload `data` to `relative_path`.

        Parameters
        ----------
        relative_path : str
            Destination under the root.
        data : bytes or file-like
            Content to upload.
        """
        parent = "/".join(str(relative_path).strip("/").split("/")[:-1])
        if parent:
            self.makedirs(parent)

        response = self._session.get(
            f"{self.base_url}/storage/put?name={self.uri(relative_path)}",
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        upload_url = response.text.strip()

        put = self._session.put(
            upload_url,
            headers={"Content-Type": "application/octet-stream"},
            data=data,
            timeout=self.timeout,
        )
        put.raise_for_status()


def open_goa_stream(spec):
    """Return a streaming response for the GOA download.

    Parameters
    ----------
    spec : dict
        Job spec, carrying ``goa_url`` and ``goa_cookie``.

    Returns
    -------
    `requests.Response`
        An unread streaming response.

    Raises
    ------
    RuntimeError
        If GOA refuses the request.

    Notes
    -----
    The cookie is set on the session rather than sent as a header, because
    that is how the archive expects it and how `astroquery/gemini.py` does it
    on the VM. Sending it any other way silently returns only public data:
    the request succeeds, the tarball is smaller, and nothing says why.
    """
    session = requests.Session()
    cookie = spec.get("goa_cookie")
    if cookie:
        session.cookies.set("gemini_archive_session", cookie, domain="archive.gemini.edu")

    response = session.get(spec["goa_url"], stream=True, timeout=spec.get("timeout", 300))
    if response.status_code != 200:
        raise RuntimeError(
            f"GOA returned HTTP {response.status_code} for {spec['goa_url']}"
        )
    return response


def _decompress(member_file, name):
    """Yield decompressed chunks of one tar member.

    Parameters
    ----------
    member_file : file-like
        The member's bytes, as the tar stream provides them.
    name : str
        Member name, used only to decide whether to decompress.

    Yields
    ------
    bytes

    Notes
    -----
    GOA ships ``.fits.bz2``. Decompressed incrementally rather than with
    `bz2.decompress`, which would hold an entire uncompressed FITS file in
    memory -- routinely hundreds of megabytes, and several concurrent jobs on
    one notebook server would exhaust it.

    Members that are not ``.bz2`` pass through untouched. The archive
    sometimes includes plain files, and refusing them would drop data the
    caller asked for.
    """
    if not name.endswith(".bz2"):
        while True:
            chunk = member_file.read(CHUNK_BYTES)
            if not chunk:
                return
            yield chunk
        return

    decompressor = bz2.BZ2Decompressor()
    while True:
        chunk = member_file.read(CHUNK_BYTES)
        if not chunk:
            return
        out = decompressor.decompress(chunk)
        if out:
            yield out


def _upload(vospace, destination, chunks, job_dir):
    """Upload `chunks` to `destination`, buffering if required.

    Returns
    -------
    int
        Bytes uploaded.

    Notes
    -----
    See `BUFFER_BEFORE_UPLOAD`. The buffered path writes a temporary file
    next to the job and removes it in `finally`, so a failure part-way
    through cannot leave proprietary bytes behind on the notebook server.
    """
    if not BUFFER_BEFORE_UPLOAD:
        # Streamed: `requests` sends a generator with chunked encoding, so
        # nothing is ever fully in memory or on disk.
        size_holder = [0]

        def counted():
            for chunk in chunks:
                size_holder[0] += len(chunk)
                yield chunk

        vospace.put(destination, counted())
        return size_holder[0]

    tmp_path = os.path.join(job_dir, ".upload.tmp")
    size = 0
    try:
        with open(tmp_path, "wb") as fh:
            for chunk in chunks:
                fh.write(chunk)
                size += len(chunk)
        with open(tmp_path, "rb") as fh:
            vospace.put(destination, fh)
        return size
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def run_download(spec, job_dir):
    """Fetch the observation and write every member into VOSpace.

    Parameters
    ----------
    spec : dict
        Job spec.
    job_dir : str
        The job directory on Data Lab.

    Returns
    -------
    dict
        Status fields for the final `write_status` call.

    Notes
    -----
    The tar is opened with ``mode="r|*"``, the *streaming* form, which reads
    forward only and never seeks. The seekable form would force the whole
    tarball to disk first, which is exactly what this runner exists to avoid.

    A member that fails to upload is recorded and the run continues. One
    corrupt file in a 200-file program should not cost the other 199, and the
    VM can see from `failures` precisely which are missing -- more useful
    than an aborted job that leaves the PI guessing.
    """
    vospace = VOSpace(
        base_url=spec["datalab_base_url"],
        token=spec["datalab_token"],
        root=spec["vospace_root"],
    )
    prefix = spec["destination_prefix"].strip("/")

    seen = 0
    kept = 0
    files = []
    failures = []
    next_progress = time.time() + PROGRESS_SECONDS

    response = open_goa_stream(spec)
    log_event(job_dir, event="download_started", url=spec["goa_url"])

    with tarfile.open(fileobj=response.raw, mode="r|*") as tar:
        for member in tar:
            if not member.isfile():
                continue
            seen += 1

            # `.fits.bz2` becomes `.fits`; the stored name must match what
            # the VM will look for, and it builds names without the `.bz2`.
            base = posixpath.basename(member.name)
            stored = base[:-4] if base.endswith(".bz2") else base
            destination = f"{prefix}/{stored}"

            try:
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                size = _upload(
                    vospace, destination, _decompress(extracted, member.name), job_dir
                )
                kept += 1
                files.append({"name": stored, "size": size})
                log_event(job_dir, event="file_written", name=stored, size=size)
            except Exception as exc:
                failures.append({"name": stored, "error": str(exc)[:300]})
                log_event(job_dir, event="file_failed", name=stored, error=str(exc)[:300])

            if time.time() >= next_progress:
                write_status(job_dir, "running", stage="downloading", seen=seen, kept=kept)
                next_progress = time.time() + PROGRESS_SECONDS

    return {
        "state": "finished",
        "seen": seen,
        "kept": kept,
        # Names and sizes only. Headers are read by the VM through the
        # storage seam, so nothing here has to be trusted about content.
        "files": files,
        "failures": failures,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default="job_spec.json")
    args = parser.parse_args()

    job_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(job_dir, args.spec)) as fh:
        spec = json.load(fh)
    # Immediately, before any work: the spec holds this PI's Data Lab token
    # and their GOA session cookie, and both are now in memory. Every second
    # they stay on disk is a second they can be read.
    scrub(job_dir, SECRET_FILES)

    write_status(job_dir, "running", stage="startup", seen=0, kept=0)

    try:
        result = run_download(spec, job_dir)
    except Exception as exc:
        write_status(
            job_dir,
            "failed",
            reason=str(exc)[:500],
            traceback=traceback.format_exc()[-4000:],
        )
        return 1
    finally:
        # In `finally` so a crash cannot leave the code behind for editing.
        scrub(job_dir, SECRET_FILES + CODE_FILES)

    write_status(job_dir, result.pop("state"), **result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
