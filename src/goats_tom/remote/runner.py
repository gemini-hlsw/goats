#!/usr/bin/env python3
"""GOATS remote runner — drains one ANTARES window on Astro Data Lab.

Staged onto a PI's Data Lab account and started detached by
`goats_tom.astro_data_lab.headless`. Runs as that PI, under their quota,
with their credentials.

**No GOATS imports.** ``mydb.py`` is staged alongside this file and imported
as a plain sibling module, so nothing here needs the ``goats_tom`` package
installed on Data Lab. It is the same file the VM uses, not a copy, so the
two sides cannot drift.

What one window does
--------------------
Fork a watchdog, drain whatever accumulated on the PI's Kafka consumer group
since last time, run their handler on each locus, append the survivors to
MyDB, commit offsets, exit. The VM later rotates the MyDB table aside and
pulls the rows into `AntaresLocus`.

Two invariants
--------------
**Offsets are committed only after a successful MyDB insert.** ANTARES tracks
offsets server-side, so a committed offset means "GOATS has this alert". With
``enable_auto_commit`` -- the client's default -- offsets advance as messages
are read, and a window that aborts mid-drain silently loses everything it had
consumed. Auto-commit is therefore disabled and `commit` is called explicitly
after each batch lands. The cost of a crash between insert and commit is a
duplicate, which the VM resolves on ``(subscription, locus_id)``; the cost of
the reverse ordering is a permanently lost alert.

**Every row carries `generation`.** A runner whose subscription has been
restarted underneath it keeps writing happily; those rows are discarded at
ingest rather than trusted. Stopping the process is best-effort, so nothing
depends on it.
"""

import argparse
import importlib.util
import json
import os
import signal
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mydb  # noqa: E402 -- staged sibling, not a GOATS import

# Kafka poll slice. Short enough that the window deadline is checked
# regularly, long enough not to spin. `poll` returns (None, None) on timeout
# rather than blocking forever, which is what makes cooperative shutdown work
# at all -- the watchdog only has to cover the cases where it does not.
POLL_SECONDS = 5.0

# Status keys preserved across writes rather than overwritten.
STICKY_KEYS = ("kafka", "kafka_config", "environment")

# Removed from the job directory as soon as they are no longer needed.
#
# Everything staged here lives on the PI's own account and is writable by
# them. Left in place it is both a credential leak (`job_spec.json` holds
# their Data Lab token and Kafka secret) and a tampering surface: a PI could
# edit `runner.py` or the spec between windows and write rows claiming
# another PI's `subscription_id`. Scrubbing shrinks that window; the VM
# refusing to trust row contents closes it.
#
# `status.json`, the logs and `watchdog.log` are deliberately kept -- they are
# the only channel by which the VM learns what happened.
SECRET_FILES = ("job_spec.json",)
CODE_FILES = ("runner.py", "mydb.py", "handler.py")

# Seconds between progress writes to `status.json`.
#
# Without these the file changes only at startup and at the end, so a window
# reports `seen=0` for its whole duration however much it is draining -- and,
# worse, the supervisor derives liveness from the status file changing, so a
# job that reports nothing for long enough is reaped as lost while working
# perfectly. Fine for a ten-minute window, fatal for a continuous one.
#
# Short, and deliberately shorter than it needs to be for liveness alone.
# Loci reach MyDB every `FLUSH_SECONDS` and the supervisor collects them
# every 15 seconds, so at 30 seconds the dashboard filled with loci while the
# counts beside it still read zero -- the panel contradicting the table it
# sits above. This is a small write to local disk, so matching the flush
# cadence costs nothing.
PROGRESS_SECONDS = 5.0

# Seconds before an accumulated batch is written, regardless of size.
#
# This, not `BATCH_SIZE`, is what normally triggers a write. Waiting for a
# fixed count meant a quiet topic held loci until the window ended -- over ten
# minutes to reach a dashboard that shows them in about a second locally.
FLUSH_SECONDS = 2.0

# Upper bound on rows per insert. A burst backstop, not the usual trigger:
# every write is an HTTP POST to the query service plus a Kafka commit, so a
# firehose sending one request per locus would leave the runner waiting on
# round trips instead of draining the stream. Each insert is followed by an
# offset commit, so this also caps how much work a crash can duplicate.
BATCH_SIZE = 200


def scrub(job_dir, names):
    """Delete `names` from `job_dir`, ignoring what is already gone.

    Notes
    -----
    Deleting a running script is safe on POSIX: the interpreter holds an open
    handle to the inode, so execution continues from the unlinked file.
    """
    for name in names:
        try:
            os.remove(os.path.join(job_dir, name))
        except OSError:
            pass


def write_status(job_dir, state, **extra):
    """Write `status.json` atomically.

    Notes
    -----
    Written via a temporary file and `os.replace` because the VM polls this
    through the contents API and would otherwise read half a file. This is
    the only channel by which a detached job reports anything, so a torn
    read looks identical to a crash.
    """
    path = os.path.join(job_dir, "status.json")
    tmp = path + ".tmp"
    payload = {"state": state, "pid": os.getpid(), "ts": time.time()}
    # Carry forward diagnostics written by earlier stages. The Kafka
    # reachability result is established first and is the most valuable thing
    # in the file, so a later failure -- a missing package, say -- must not
    # overwrite it with a status that omits it.
    for key in STICKY_KEYS:
        if key not in extra:
            try:
                with open(path) as fh:
                    previous = json.load(fh)
                if key in previous:
                    payload[key] = previous[key]
            except Exception:
                pass
    payload.update(extra)
    with open(tmp, "w") as fh:
        json.dump(payload, fh)
    os.replace(tmp, path)


def spawn_watchdog(job_dir, deadline_seconds):
    """Fork a process that kills this one if it outlives its window.

    Notes
    -----
    Forked before any network or Kafka work, so it exists no matter where the
    parent later blocks. It shares no locks and does no I/O that can stall:
    its only job is to outlive a wedged parent.

    Polls for the parent rather than sleeping the full deadline, so a window
    that finishes in thirty seconds does not leave a process idling for the
    remaining nine and a half minutes. Across 300 PIs at six windows an hour
    that difference is the whole point.
    """
    parent = os.getpid()
    if os.fork() != 0:
        return

    end = time.time() + deadline_seconds
    while time.time() < end:
        time.sleep(2)
        try:
            os.kill(parent, 0)  # liveness probe; sends no signal
        except ProcessLookupError:
            os._exit(0)  # parent finished cleanly, nothing to do
    try:
        os.kill(parent, signal.SIGKILL)
        with open(os.path.join(job_dir, "watchdog.log"), "w") as fh:
            fh.write(
                "watchdog killed pid %d after %ss\n" % (parent, deadline_seconds)
            )
    except ProcessLookupError:
        pass
    os._exit(0)


def extend_sys_path(paths):
    """Append `paths` to ``sys.path`` and report what became importable.

    Parameters
    ----------
    paths : iterable of str
        Directories to append.

    Returns
    -------
    dict
        Python version, the paths added, and where key modules resolved from.

    Notes
    -----
    A stopgap until Data Lab has a dedicated GOATS kernel. The antares kernel
    is the one whose Kafka SSL works, but it has no ``dl``, so ``dl`` is
    borrowed from another environment's ``site-packages``.

    **Appended, never prepended.** The kernel's own packages must keep
    winning: the borrowed directory belongs to a different Python minor
    version, so anything with a compiled extension there was built for the
    wrong interpreter and will not import. Appending means only genuinely
    missing modules -- ``dl`` and any pure-Python dependency it needs -- are
    taken from it, while numpy, astropy and requests continue to come from
    the kernel.

    That is also the narrow risk worth watching: if ``dl`` needs a dependency
    the kernel lacks *and* that dependency is compiled, this will fail. The
    returned origins make that visible rather than mysterious.
    """
    report = {"python": sys.version.split()[0], "added": []}
    for path in paths or ():
        if path and path not in sys.path:
            sys.path.append(path)
            report["added"].append(path)

    # Checked explicitly: `import dl` can succeed while `dl.queryClient`
    # fails on a transitive dependency, and finding that out at startup beats
    # finding it out mid-window.
    try:
        from dl import queryClient  # noqa: F401
        report["dl_queryclient"] = "ok"
    except Exception as exc:
        report["dl_queryclient"] = "%s: %s" % (type(exc).__name__, exc)

    origins = {}
    for name in ("dl", "antares_client", "numpy", "requests", "pandas",
                 "astropy", "specutils"):
        try:
            module = __import__(name)
            origins[name] = {
                "file": getattr(module, "__file__", "?"),
                "version": getattr(module, "__version__", "?"),
            }
        except Exception as exc:
            origins[name] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    report["modules"] = origins
    return report


def kafka_preflight(timeout=8.0):
    """Report whether ANTARES' Kafka brokers are reachable from here.

    Returns
    -------
    dict
        ``{"reachable": bool|None, "brokers": [...], "detail": str}``.
        `None` means the check itself could not run, which is not the same
        as unreachable.

    Notes
    -----
    Recorded on every window because a drain of zero loci is ambiguous
    otherwise: a quiet topic and a blocked port look identical from the
    outside. Data Lab having outbound internet usually means HTTPS on 443;
    Kafka needs SASL_SSL on 9092, which can be firewalled separately. If
    that port is closed the whole offload is dead at the foundation, so it
    is worth knowing explicitly rather than inferring from silence.

    `fetch_config` ignores ``self``, so it is called unbound to avoid
    constructing a Consumer just to learn the broker list.
    """
    import socket

    try:
        from antares_client.stream import KafkaStreamingClient

        options = KafkaStreamingClient.fetch_config(None)["options"]
        brokers = [b.strip() for b in options.get("bootstrap.servers", "").split(",")]
        brokers = [b for b in brokers if b]
    except Exception as exc:
        return {"reachable": None, "brokers": [], "detail": "no broker list: %s" % exc}

    if not brokers:
        return {"reachable": None, "brokers": [], "detail": "empty broker list"}

    results = []
    for broker in brokers:
        host, _, port = broker.rpartition(":")
        try:
            sock = socket.create_connection((host, int(port or 9092)), timeout)
            sock.close()
            results.append("%s ok" % broker)
        except Exception as exc:
            results.append("%s FAILED (%s)" % (broker, exc))
    return {
        "reachable": all("ok" in r for r in results),
        "brokers": brokers,
        "detail": "; ".join(results),
    }


# Set by main() so the Kafka patch can dump diagnostics next to the logs.
_JOB_DIR = [os.getcwd()]

# Kafka options dropped from the config ANTARES serves.
#
# ANTARES pins `ssl.cipher.suites` to a list that OpenSSL 3.x refuses:
#
#   ssl.cipher.suites failed: error:0A0000B9:SSL routines::no cipher match
#
# The kernel with `dl` installed is new enough to have OpenSSL 3, while the
# older antares kernel is not -- so this is exactly the kernel we need to
# use. Dropping the option lets librdkafka negotiate its own ciphers with
# the broker, which is what an unpinned client would do anyway.
# Empty by default. On the `python3` kernel, OpenSSL 3 rejects the cipher
# list ANTARES pins and this must be set to ``["ssl.cipher.suites"]``; on the
# antares kernel the served config works natively, and stripping a setting
# that is doing its job would be a change for no reason. Driven from the job
# spec via ``strip_kafka_options`` so it can be turned on without a code
# change. The config is dumped either way -- see `build_streaming_client`.
STRIP_KAFKA_OPTIONS = ()


def build_streaming_client(spec, strip=STRIP_KAFKA_OPTIONS):
    """Construct a `StreamingClient`, dropping unusable server-sent options.

    Parameters
    ----------
    spec : dict
        Job spec.
    strip : iterable of str, optional
        Config keys to remove before librdkafka sees them.

    Returns
    -------
    tuple
        ``(client, report)``. `report` records the client version, the option
        keys ANTARES served, and what was removed.

    Notes
    -----
    Patched at ``confluent_kafka.Consumer`` rather than at the client's
    `fetch_config`, because that is the single line every code path must go
    through::

        default_config = self.fetch_config()["options"]
        kafka_config = {..., **default_config}
        self._consumer = confluent_kafka.Consumer(kafka_config)

    Overriding `fetch_config` also works on the current release, but it
    depends on *where* the config is assembled -- a detail that has no
    stability guarantee and would fail silently if it moved. Intercepting the
    consumer constructor depends only on the config eventually reaching
    librdkafka, which it must. `stream.py` looks up
    ``confluent_kafka.Consumer`` as a module attribute at call time, so
    replacing it is enough; no import order games are needed.

    The config is edited in place as well as by replacement, since the caller
    holds its own reference to the same dict.
    """
    import confluent_kafka

    from antares_client.stream import KafkaStreamingClient

    report = {"removed": {}, "served_options": [], "patched": "Consumer"}
    try:
        import antares_client

        report["antares_client_version"] = getattr(
            antares_client, "__version__", "unknown"
        )
    except Exception:
        report["antares_client_version"] = "unknown"

    original_consumer = confluent_kafka.Consumer

    def _strip_in_place(mapping, path=""):
        """Remove `strip` keys from `mapping`, recursing into sub-dicts.

        Notes
        -----
        Recursive and whitespace-tolerant because a flat, exact-match removal
        can miss the key two ways, both silent: librdkafka accepts nested
        config blocks such as ``default.topic.config``, and a served key with
        stray whitespace will not compare equal to a literal.
        """
        wanted = {k.strip().lower() for k in strip}
        for key in list(mapping):
            value = mapping[key]
            if isinstance(key, str) and key.strip().lower() in wanted:
                report["removed"][f"{path}{key}"] = str(mapping.pop(key))[:200]
                continue
            if isinstance(value, dict):
                _strip_in_place(value, path=f"{path}{key}.")

    def _patched_consumer(config, *args, **kwargs):
        if isinstance(config, dict):
            # Dumped verbatim (minus secrets) so the exact config librdkafka
            # receives is inspectable instead of inferred.
            redacted = {
                k: ("<redacted>" if "password" in k or "username" in k
                    or "secret" in k else v)
                for k, v in config.items()
                if not callable(v)
            }
            report["served_config"] = {k: str(v)[:200] for k, v in redacted.items()}
            _strip_in_place(config)
            report["final_options"] = sorted(str(k) for k in config)
            # Written unconditionally: knowing what librdkafka received is
            # just as useful when the connection succeeds.
            try:
                with open(os.path.join(_JOB_DIR[0], "kafka_config.json"), "w") as fh:
                    json.dump(report, fh, indent=2, default=str)
            except Exception:
                pass
        return original_consumer(config, *args, **kwargs)

    confluent_kafka.Consumer = _patched_consumer
    try:
        client = KafkaStreamingClient(
            spec["topics"],
            api_key=spec["kafka_key"],
            api_secret=spec["kafka_secret"],
            # Fixed per subscription. The client defaults to the hostname,
            # which on Data Lab differs between runs -- a new group id resets
            # offsets, so every window would replay the whole backlog.
            group=spec["consumer_group"],
            # The default is True and would lose alerts on an aborted window.
            enable_auto_commit=False,
        )
    finally:
        confluent_kafka.Consumer = original_consumer
    return client, report


def build_rsp_tap_service(token):
    """Build a `pyvo.dal.TAPService` for the Rubin Science Platform.

    Parameters
    ----------
    token : str or None
        The PI's RSP access token, passed in the job spec.

    Returns
    -------
    `pyvo.dal.TAPService` or None
        `None` if no token was supplied or the service cannot be built.
        Handlers must check for `None`, exactly as they do locally.

    Notes
    -----
    Mirrors `goats_tom.antares_locus_handler.build_rsp_tap_service`: the
    token goes in as an HTTP Basic Auth password with username
    ``x-oauth-basic``, per RSP's external-access documentation.

    Duplicated rather than imported because this file runs on Data Lab with
    no `goats_tom` package available. The two must be changed together, and
    the shared piece -- the token itself -- travels in the job spec.

    Returning `None` on failure rather than raising is deliberate: an
    unreachable TAP service is an environment problem, not a fault in the
    PI\'s handler, and raising here would abort the window and mark the
    subscription unhealthy for something they did not do.
    """
    if not token:
        return None
    try:
        import pyvo
        from pyvo.auth import AuthSession

        session = AuthSession()
        session.credentials.set_password("x-oauth-basic", token)
        return pyvo.dal.TAPService(
            "https://data.lsst.cloud/api/tap", session=session
        )
    except Exception:
        return None


def load_handler(path, extra_globals=None):
    """Import the PI's handler module and return its ``myfilter``.

    Raises
    ------
    ValueError
        If the module defines no callable ``myfilter``.

    Notes
    -----
    Imported normally, with no restricted namespace. Sandboxing was never
    what protected GOATS here -- the code already ran with the PI's own
    privileges. On Data Lab it runs under their account and quota, which is
    the actual isolation, so the import ban and pre-bound namespace that the
    local path needs are unnecessary and would only break handlers that use
    the Data Lab stack.
    """
    spec = importlib.util.spec_from_file_location("goats_handler", path)
    module = importlib.util.module_from_spec(spec)
    # Injected before execution so module-level code can use them too, and
    # so a handler referring to `RSP_tap_service` resolves the same name it
    # would locally.
    for name, value in (extra_globals or {}).items():
        setattr(module, name, value)
    spec.loader.exec_module(module)
    handler = getattr(module, "myfilter", None)
    if not callable(handler):
        raise ValueError("handler defines no callable 'myfilter'")
    return handler


class Stamper(object):
    """Hands out strictly increasing `written_at` values.

    Notes
    -----
    The VM drains a table by paging on ``written_at > watermark``, so two
    rows sharing a value would put one of them permanently out of reach.
    Wall-clock time alone is not enough: several loci can be written inside
    the same clock tick. Each stamp is therefore forced at least a
    microsecond past the previous one, which keeps the sequence monotonic
    while staying close to real time for debugging.
    """

    def __init__(self):
        self._last = 0.0

    def next(self):
        value = time.time()
        if value <= self._last:
            value = self._last + 1e-6
        self._last = value
        return value


def locus_to_row(locus, topic, spec, now):
    """Flatten a `Locus` into a MyDB row.

    Notes
    -----
    Reads defensively. Alert properties are sparse and vary by survey, so a
    missing magnitude is normal rather than exceptional and must not abort a
    window -- unlike a handler raising, which means the PI's code is wrong.
    """
    props = getattr(locus, "properties", None) or {}

    def prop(*names):
        for name in names:
            if name in props and props[name] is not None:
                return props[name]
        return None

    return {
        "locus_id": getattr(locus, "locus_id", None) or getattr(locus, "id", None),
        "subscription_id": spec["subscription_id"],
        "generation": spec["generation"],
        "run_number": spec.get("run_number", 0),
        "ra": getattr(locus, "ra", None),
        "dec": getattr(locus, "dec", None),
        "mjd": prop("newest_alert_observation_time", "mjd"),
        "magnitude": prop("newest_alert_magnitude", "mag"),
        "passband": prop("newest_alert_passband", "passband") or "",
        "topic": topic or "",
        "latest_alert_id": prop("newest_alert_id") or "",
        "in_tns": bool(prop("in_tns")),
        # Strictly increasing; the VM pages on this when draining.
        "written_at": now,
    }


def run_window(spec, job_dir):
    """Drain one window. Returns a status dict."""
    table = spec.get("table", "goats_loci")
    deadline = time.time() + float(spec["window_seconds"])
    db = mydb.MyDBClient(spec["datalab_token"])
    db.ensure_table(table)

    handler = load_handler(
        os.path.join(job_dir, "handler.py"),
        {"RSP_tap_service": build_rsp_tap_service(spec.get("rsp_token"))},
    )

    client, kafka_report = build_streaming_client(
        spec, strip=tuple(spec.get("strip_kafka_options", STRIP_KAFKA_OPTIONS))
    )
    # Recorded whether or not anything was removed: if the connection still
    # fails, knowing exactly which options librdkafka received is the
    # difference between diagnosing it and guessing.
    write_status(job_dir, "running", stage="draining",
                 kafka_config=kafka_report, seen=0, kept=0)

    seen = kept = 0
    batch = []
    stamp = Stamper()

    def flush():
        """Insert the batch, then commit offsets. Order matters."""
        if not batch:
            return
        db.insert_rows(table, batch)
        client.commit()
        del batch[:]

    def maybe_flush(now):
        """Write the batch if it is full or has waited long enough."""
        nonlocal next_flush
        if batch and (len(batch) >= BATCH_SIZE or now >= next_flush):
            flush()
            next_flush = now + FLUSH_SECONDS

    next_progress = time.time() + PROGRESS_SECONDS
    next_flush = time.time() + FLUSH_SECONDS

    try:
        while time.time() < deadline:
            topic, locus = client.poll(timeout=POLL_SECONDS)

            # Written on a timer rather than per locus: it is the only
            # liveness signal the supervisor has, so it must keep ticking
            # through quiet stretches when no locus arrives at all.
            if time.time() >= next_progress:
                write_status(job_dir, "running", stage="draining",
                             seen=seen, kept=kept)
                next_progress = time.time() + PROGRESS_SECONDS

            if locus is None:
                # Flush here too: without this, a locus arriving just before
                # a quiet stretch waits for the *next* locus before being
                # written, which on a slow topic could be minutes.
                maybe_flush(time.time())
                continue
            seen += 1
            try:
                keep = handler(locus)
            except Exception:
                # Abort the window without committing, so these alerts are
                # redelivered once the PI fixes their handler. Aborting is
                # deliberate: silently skipping would let a handler that is
                # broken for most loci look healthy while quietly missing
                # science.
                flush_failed = None
                try:
                    flush()  # keep what already passed
                except Exception as exc:
                    flush_failed = str(exc)
                return {
                    "state": "failed",
                    "unhealthy": True,
                    "reason": "handler raised",
                    "locus_id": getattr(locus, "locus_id", None),
                    "traceback": traceback.format_exc()[-4000:],
                    "seen": seen,
                    "kept": kept,
                    "flush_error": flush_failed,
                }
            if keep:
                batch.append(locus_to_row(locus, topic, spec, stamp.next()))
                kept += 1
            maybe_flush(time.time())
        flush()
        return {"state": "finished", "seen": seen, "kept": kept}
    finally:
        try:
            client.close()
        except Exception:
            pass


def preview(spec, job_dir):
    """Run the handler against one locus and report the outcome.

    Notes
    -----
    Preview happens here rather than on the VM because handlers import from
    the **Data Lab** stack. Evaluating them server-side would produce both
    false passes and false failures.
    """
    from antares_client import search

    handler = load_handler(
        os.path.join(job_dir, "handler.py"),
        {"RSP_tap_service": build_rsp_tap_service(spec.get("rsp_token"))},
    )
    locus = search.get_by_id(spec["preview_locus_id"])
    if locus is None:
        return {"state": "failed", "reason": "locus not found"}
    try:
        result = handler(locus)
    except Exception:
        return {"state": "failed", "traceback": traceback.format_exc()[-4000:]}
    return {"state": "finished", "result": bool(result)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default="job_spec.json")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    job_dir = os.path.dirname(os.path.abspath(__file__))
    _JOB_DIR[0] = job_dir
    with open(os.path.join(job_dir, args.spec)) as fh:
        spec = json.load(fh)
    # Immediately, before any work: the spec holds this PI's Data Lab token
    # and ANTARES secret, and it is now in memory. Every second it stays on
    # disk is a second it can be read.
    scrub(job_dir, SECRET_FILES)

    # Before importing anything that needs the borrowed path.
    env_report = extend_sys_path(spec.get("extra_sys_path"))

    # Before anything that can block.
    spawn_watchdog(job_dir, float(spec.get("deadline_seconds", 900)))
    write_status(job_dir, "running", stage="startup", environment=env_report,
                 seen=0, kept=0)

    # Run first, and recorded stickily, so its answer survives whatever fails
    # later. Kafka reachability is the foundational assumption of the whole
    # offload; learning it should not depend on the rest of the run working.
    preflight = kafka_preflight()
    write_status(job_dir, "running", stage="preflight", kafka=preflight,
                 seen=0, kept=0)
    if preflight["reachable"] is False:
        write_status(job_dir, "failed", kafka=preflight,
                     reason="ANTARES Kafka brokers unreachable from Data Lab")
        return 1

    try:
        result = preview(spec, job_dir) if args.preview else run_window(spec, job_dir)
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
