#!/usr/bin/env python3
"""GOATS reduction runner — runs one DRAGONS reduction on Astro Data Lab.

Staged onto a PI's Data Lab account and started detached by
`goats_tom.astro_data_lab.headless`. Runs as that PI, under their quota,
against their own files.

**No GOATS imports.** Only the standard library, ``requests``, and DRAGONS
itself, which has to be present on the Data Lab kernel. `preflight` checks
that before anything else and fails with a message naming the missing
package, because "no module named gempy" arriving from a detached process an
hour later is not a debuggable error.

Where the files are
-------------------
Three different places, and the distinction is the whole design:

- **Inputs** are read from ``~/vospace/…``, the read-only view of the PI's
  VOSpace that JupyterLab provides. Real POSIX paths, so DRAGONS opens them
  directly with no fetch step.
- **The run folder** is in the notebook home, which is writable. It has to
  be: `Reduce` writes intermediate products, and ``cal_manager.db`` is
  SQLite, needing write access, seeks and file locking. An HTTP object API
  provides none of those and neither does a read-only mount.
- **Outputs** are uploaded to VOSpace when the reduction finishes.

This is what resolves the calibration-database blocker recorded in
``STATUS.md``. `add_cal` stores an absolute path *into* the caldb, which
outlives the call; on the VM under a remote backend that path was a
temporary file already deleted. Here the caldb and the files it points at
are on the same real filesystem for the whole run.
"""

import argparse
import json
import os
import sys
import time
import traceback

import requests

#: Seconds between progress writes to `status.json`.
PROGRESS_SECONDS = 5.0

SECRET_FILES = ("job_spec.json",)
CODE_FILES = ("reduction_runner.py",)


def write_status(job_dir, state, **extra):
    """Write `status.json` atomically. See the download runner."""
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
    This is how DRAGONS output reaches the GOATS UI. Locally a
    `logging.Handler` pushes lines into a Channels group; that handler runs
    in the same process as the reduction and cannot exist here. The VM tails
    this file with `tail_ndjson` and republishes.

    Every line is written from the start of the run, so what the PI sees is
    the whole stream and not a tail of it -- which is the bar the local
    experience sets.
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


def preflight():
    """Check DRAGONS is importable before doing anything else.

    Returns
    -------
    dict
        ``{"ok": bool, "missing": [str], "versions": {...}}``.

    Notes
    -----
    Run first and reported stickily, because the whole of Phase 4 rests on
    DRAGONS being present on the Data Lab kernel and that is not something
    GOATS controls. Learning it should not depend on the rest of the run
    working.
    """
    report = {"ok": True, "missing": [], "versions": {}}
    for name in ("astrodata", "gempy", "recipe_system"):
        try:
            module = __import__(name)
            report["versions"][name] = getattr(module, "__version__", "unknown")
        except Exception:
            report["ok"] = False
            report["missing"].append(name)
    return report


class VOSpace:
    """Minimal Data Lab storage client, for uploading outputs.

    Notes
    -----
    Duplicated from the download runner rather than shared. Each runner is
    staged onto Data Lab as a **single self-contained file**; a shared module
    would be a third file to stage and keep in step, for two short methods.
    The GOATS-side client is not usable here at all -- it lives in a package
    that is not installed on Data Lab.
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
        relative_path = str(relative_path).strip("/")
        return f"{self.root}/{relative_path}" if relative_path else self.root

    def makedirs(self, relative_path):
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

    def put(self, relative_path, fileobj):
        parent = "/".join(str(relative_path).strip("/").split("/")[:-1])
        if parent:
            self.makedirs(parent)
        response = self._session.get(
            f"{self.base_url}/storage/put?name={self.uri(relative_path)}",
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        put = self._session.put(
            response.text.strip(),
            headers={"Content-Type": "application/octet-stream"},
            data=fileobj,
            timeout=self.timeout,
        )
        put.raise_for_status()


def _attach_log_bridge(job_dir):
    """Route DRAGONS's logging into the NDJSON event file.

    Notes
    -----
    Mirrors what `DRAGONSHandler` does on the VM: attaches to the root
    logger, so anything DRAGONS emits is captured whatever logger it uses.
    DRAGONS configures logging in several places and attaching to a named
    logger catches only some of it.

    Failures here are swallowed. A reduction that runs but reports nothing
    is a bad outcome; a reduction that refuses to start because its log
    plumbing failed is a worse one.
    """
    import logging  # noqa: PLC0415

    class NDJSONHandler(logging.Handler):
        def emit(self, record):
            try:
                log_event(
                    job_dir,
                    event="log",
                    level=record.levelname,
                    message=self.format(record),
                )
            except Exception:
                pass

    handler = NDJSONHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)


def run_reduction(spec, job_dir):
    """Run `Reduce` over the inputs and upload what it produces.

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
    The output directory is created under the job directory in the notebook
    home, and `os.chdir` into it, because `Reduce` writes relative to the
    working directory. Running from elsewhere scatters intermediates across
    the home directory with no way to tell which run made them.

    The caldb is initialised **in that directory**, so `add_cal` records
    paths that stay valid for the run -- the point of doing this here at all.

    Inputs are used at their `~/vospace/...` paths directly, with no copy.
    They are read-only, which is all DRAGONS needs of an input, and copying
    a few tens of gigabytes to reduce it once would be a poor trade.
    """
    from recipe_system import cal_service  # noqa: PLC0415
    from recipe_system.reduction.coreReduce import Reduce  # noqa: PLC0415

    output_dir = os.path.join(job_dir, "outputs")
    os.makedirs(output_dir, exist_ok=True)
    os.chdir(output_dir)

    caldb_path = os.path.join(output_dir, "cal_manager.db")
    caldb = cal_service.set_local_database()
    caldb.init(wipe=False)
    log_event(job_dir, event="caldb_ready", path=caldb_path)

    inputs = [os.path.expanduser(path) for path in spec["input_paths"]]
    missing = [path for path in inputs if not os.path.exists(path)]
    if missing:
        raise RuntimeError(
            f"{len(missing)} input file(s) not present on the VOSpace mount, "
            f"first missing: {missing[0]}"
        )

    for path in spec.get("calibration_paths", []):
        expanded = os.path.expanduser(path)
        if os.path.exists(expanded):
            caldb.add_cal(expanded)
            log_event(job_dir, event="caldb_added", path=expanded)

    write_status(job_dir, "running", stage="reducing", seen=len(inputs), kept=0)

    reduce_instance = Reduce()
    reduce_instance.files = inputs
    if spec.get("recipe_name"):
        reduce_instance.recipename = spec["recipe_name"]
    if spec.get("uparms"):
        reduce_instance.uparms = spec["uparms"]

    reduce_instance.runr()
    log_event(job_dir, event="reduce_finished")

    # Upload whatever `Reduce` left behind. Enumerated after the run rather
    # than predicted from the recipe: which files a recipe produces depends
    # on the data and the primitives it chose, and a predicted list would
    # silently drop anything unexpected.
    vospace = VOSpace(
        base_url=spec["datalab_base_url"],
        token=spec["datalab_token"],
        root=spec["vospace_root"],
    )
    prefix = spec["destination_prefix"].strip("/")

    uploaded = []
    failures = []
    for name in sorted(os.listdir(output_dir)):
        path = os.path.join(output_dir, name)
        if not os.path.isfile(path):
            continue
        # The caldb is derived, not science data, and is rebuilt by the next
        # run. Uploading a live SQLite file would also risk copying it
        # mid-write.
        if name == "cal_manager.db" and not spec.get("upload_caldb"):
            continue
        try:
            with open(path, "rb") as fh:
                vospace.put(f"{prefix}/{name}", fh)
            # `written_at` is recorded per file, at the moment that file was
            # written, and is the only record of it that will ever exist:
            # VOSpace does not report modification times, so nothing can
            # recover this afterwards.
            #
            # Per file, not per job, because a run is not one reduction. A
            # recipe can be rerun repeatedly within the same run, and each
            # rerun rewrites some outputs and leaves others untouched. One
            # timestamp for the whole job would stamp every file with the
            # job's finish time and make outputs from an earlier rerun look
            # as though the latest one produced them.
            uploaded.append(
                {
                    "name": name,
                    "size": os.path.getsize(path),
                    "written_at": time.time(),
                }
            )
            log_event(job_dir, event="output_written", name=name)
        except Exception as exc:
            failures.append({"name": name, "error": str(exc)[:300]})
            log_event(job_dir, event="output_failed", name=name, error=str(exc)[:300])

    return {
        "state": "finished",
        "seen": len(inputs),
        "kept": len(uploaded),
        "outputs": uploaded,
        "failures": failures,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default="job_spec.json")
    args = parser.parse_args()

    job_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(job_dir, args.spec)) as fh:
        spec = json.load(fh)
    scrub(job_dir, SECRET_FILES)

    _attach_log_bridge(job_dir)
    write_status(job_dir, "running", stage="startup", seen=0, kept=0)

    # First, and reported before anything else can fail: DRAGONS being
    # present on the Data Lab kernel is the assumption Phase 4 rests on, and
    # it is not something GOATS controls.
    report = preflight()
    write_status(job_dir, "running", stage="preflight", dragons=report, seen=0, kept=0)
    if not report["ok"]:
        write_status(
            job_dir,
            "failed",
            dragons=report,
            reason=(
                "DRAGONS is not available on this Data Lab kernel: missing "
                + ", ".join(report["missing"])
            ),
        )
        return 1

    try:
        result = run_reduction(spec, job_dir)
    except Exception as exc:
        write_status(
            job_dir,
            "failed",
            reason=str(exc)[:500],
            traceback=traceback.format_exc()[-4000:],
        )
        return 1
    finally:
        scrub(job_dir, SECRET_FILES + CODE_FILES)

    write_status(job_dir, result.pop("state"), **result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
