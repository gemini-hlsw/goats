"""Astro Data Lab MyDB access for the pull-only return path.

Server-deployment only; never imported in ``local`` mode.

The runner on Data Lab appends rows to a table in the PI's own MyDB. The
GOATS VM polls that table, upserts into `AntaresLocus`, and reclaims the
space. Nothing is pushed, so the VM needs no inbound API, no ingest token and
no public certificate -- it only ever makes outbound calls.

Cleanup is **rotation**, not deletion. The Data Lab query service accepts
only SELECT: ``DELETE ... WHERE`` and ``UPDATE`` are both refused with "The
specified query has invalid syntax" regardless of how the table is named. So
the VM renames the table aside, recreates an empty one for the runner to keep
writing to, drains the renamed copy, and drops it. See `rotate_for_drain`.

Notes
-----
Wraps the official ``dl`` client rather than calling the query service over
HTTP directly. The REST surface is not something to guess at, and
``astro-datalab`` is the supported entry point.

**MyDB space belongs to the PI**, not to GOATS. Filling it breaks their own
science work, so the VM must delete rows once they are safely in
`AntaresLocus` -- and only then. `delete_below` is called after a confirmed
upsert, never before.
"""

__all__ = ["LOCI_SCHEMA", "MyDBClient", "MyDBError", "loci_table_name"]

import csv
import io
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MyDBError(RuntimeError):
    """Raised when a MyDB operation fails."""


# Column order is significant: `insert_rows` emits CSV in this order.
#
# `written_at` is the watermark -- a unix epoch float with microsecond
# resolution, stamped by the runner. The VM orders by it, and deletes at or
# below the highest value it has actually consumed. A plain timestamp would
# tie too easily; a serial column would be nicer still, but MyDB tables are
# created from a flat column/type mapping with no sequence support.
#
# `generation` travels on every row so a stale runner's writes can be
# discarded at ingest rather than trusted. This is the same fencing token the
# local path already uses, carried across the boundary.
LOCI_SCHEMA: dict[str, str] = {
    "locus_id": "text",
    "subscription_id": "integer",
    "generation": "integer",
    "run_number": "integer",
    "ra": "double precision",
    "dec": "double precision",
    "mjd": "double precision",
    "magnitude": "double precision",
    "passband": "text",
    "topic": "text",
    "in_tns": "boolean",
    "written_at": "double precision",
}


def loci_table_name(prefix: str = "goats") -> str:
    """Return the MyDB table name GOATS writes loci to.

    Parameters
    ----------
    prefix : str, optional
        Table-name prefix.

    Returns
    -------
    str
        Table name, unqualified -- MyDB scopes it to the owning account.

    Notes
    -----
    One persistent table per PI, not one per run. Runs are distinguished by
    the `generation` and `run_number` columns, which keeps the table count
    fixed no matter how many windows execute.
    """
    return f"{prefix}_loci"


class MyDBClient:
    """Read and write a PI's MyDB tables.

    Parameters
    ----------
    token : str
        Data Lab auth token for the account whose MyDB is being used.

    Raises
    ------
    MyDBError
        If ``astro-datalab`` is not installed.

    Notes
    -----
    Used from both sides, with different halves exercised. The runner on Data
    Lab calls `ensure_table` and `insert_rows`; the VM calls `select_since`
    and `delete_below`.
    """

    def __init__(
        self, token: str, timeout: int = 120, probe_timeout: int = 30
    ) -> None:
        try:
            from dl import queryClient  # noqa: PLC0415 -- optional, server only
        except Exception as exc:
            # Deliberately broad, and the message carries the original error.
            #
            # `import dl` succeeding does not mean `dl.queryClient` will:
            # the submodule pulls in further dependencies, and on Data Lab
            # `dl` may be borrowed from another interpreter's site-packages,
            # where a transitive dependency can be missing or compiled for
            # the wrong Python. Reporting only "install astro-datalab" when
            # `dl` is plainly installed sends you looking in the wrong place.
            raise MyDBError(
                "Could not import dl.queryClient: %s: %s. "
                "If `dl` itself imports, this is a dependency of queryClient "
                "-- check sys.path for a package built against a different "
                "Python version." % (type(exc).__name__, exc)
            ) from exc
        self._qc = queryClient
        # The underlying client object, needed to reach `_mydb_create`
        # directly -- see `ensure_table` for why the public wrapper is
        # unusable.
        self._impl = getattr(queryClient, "client", None) or getattr(
            queryClient, "qc_client", None
        )
        self.token = token
        # `query` has no client-side timeout by default, so a service that
        # stalls -- which a table in a bad state can cause -- hangs the
        # caller forever. On the VM that would wedge the supervisor.
        self.timeout = timeout
        # Existence probes get a shorter fuse than data reads. A table whose
        # relation is missing can stall the service, and waiting the full
        # data timeout to learn that turns a diagnosis into a hang.
        self.probe_timeout = probe_timeout

    # -- schema ------------------------------------------------------------

    def list_tables(self) -> list[str]:
        """Return the tables present in this account's MyDB."""
        try:
            raw = self._qc.mydb_list(self.token)
        except Exception as exc:
            raise MyDBError(f"Could not list MyDB tables: {exc}") from exc
        if isinstance(raw, str):
            return [line.strip() for line in raw.splitlines() if line.strip()]
        return list(raw or [])

    def describe(
        self, table: str, timeout: Optional[int] = None, retries: int = 3
    ) -> list[str]:
        """Return `table`'s column names, or empty if it cannot be read.

        Parameters
        ----------
        table : str
            Table name.
        timeout : int, optional
            Per-attempt timeout; defaults to `probe_timeout`.
        retries : int, optional
            Attempts before giving up.

        Returns
        -------
        list of str
            Column names, empty if the table is unreadable or absent.

        Notes
        -----
        Asks the ``list`` endpoint first and only falls back to a query.
        ``SELECT * ... LIMIT 0`` looked like the obvious probe but is not
        dependable: on a freshly created, empty table it can come back with
        no header at all, which reads as "no columns" and is
        indistinguishable from a broken table.

        Retried with a short pause because table creation is not immediately
        visible -- the catalog entry and the queryable relation do not appear
        in the same instant, so a check run straight after `mydb_create` can
        see nothing through no fault of the table.
        """
        for attempt in range(retries):
            columns = self._describe_once(table, timeout)
            if columns:
                return columns
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
        return []

    def _describe_once(self, table: str, timeout: Optional[int]) -> list[str]:
        """One attempt at reading `table`'s columns."""
        # Preferred: the list endpoint reports a named table's schema.
        try:
            raw = self._qc.mydb_list(self.token, table=table)
            columns = _parse_schema_listing(raw)
            if columns:
                return columns
        except Exception:
            logger.debug("mydb_list failed for %r.", table, exc_info=True)

        # Fallback: a zero-row select, whose header may or may not arrive.
        try:
            raw = self._qc.query(
                self.token,
                sql=f"SELECT * FROM mydb://{table} LIMIT 0",  # noqa: S608
                fmt="csv",
                timeout=timeout or self.probe_timeout,
            )
        except Exception:
            return []
        return next(csv.reader(io.StringIO(raw or "")), [])

    def ensure_table(
        self, table: str, schema: Optional[dict[str, str]] = None
    ) -> bool:
        """Create `table` if it does not already exist.

        Parameters
        ----------
        table : str
            Table name.
        schema : dict, optional
            Column-name to PostgreSQL-type mapping; defaults to
            `LOCI_SCHEMA`.

        Returns
        -------
        bool
            Whether the table was created by this call.

        Raises
        ------
        MyDBError
            If the created table's columns do not match `schema`.

        Notes
        -----
        Three defects in the ``dl`` client shape this method, all silent:

        1. `mydb_create` accepts a schema only as a CSV string or an
           `OrderedDict`. A plain ``dict`` matches neither branch, so the
           schema is **discarded** and a table is created with no columns.
           The failure surfaces much later as "extra data after last expected
           column" on the first insert. This method therefore sends CSV text.
        2. `mydb_create` checks for failure with ``r.content[:5].lower() ==
           'error'``, comparing bytes to str -- always ``False`` on Python 3.
           It returns ``'OK'`` regardless, so its return value carries no
           information and the result is verified with `describe` instead.
        3. `drop` defaults to **True**. On an existing table that would
           destroy rows the VM has not yet consumed, so ``drop=False`` is
           always passed explicitly rather than left to the default.
        """
        schema = schema or LOCI_SCHEMA

        # Existence is decided by whether the table can actually be read,
        # not by whether it is listed. A `mydb_create` that fails partway
        # registers the name in MyDB's catalog without creating the relation:
        # `mydb_list` then reports the table while Postgres answers
        # `relation "..." not known`, and `mydb_drop` cannot remove it
        # because there is nothing there to remove.
        columns = self.describe(table)
        if sorted(columns) == sorted(schema):
            return False

        listed = any(table == t.strip() for t in self.list_tables())
        if columns:
            # Readable, but not the schema we expect. Something else owns
            # this name; refuse rather than destroy it.
            raise MyDBError(
                f"MyDB table {table!r} exists with unexpected columns "
                f"{columns}, expected {list(schema)}. Rename or remove it."
            )

        # Unreadable: either genuinely absent, or a phantom catalog entry
        # from a create that failed part-way.
        #
        # `queryClient.mydb_create` is called through its private
        # implementation rather than the public wrapper, because the public
        # three-argument form throws the token away::
        #
        #     def mydb_create(token, table, schema, **kw):
        #         return qc_client._mydb_create(token=def_token(None), ...)
        #                                             ^^^^^^^^^^^^^^^
        #
        # `def_token(None)` resolves whatever ambient login the environment
        # happens to have. In an interactive Data Lab notebook that is the
        # user's own session, so creation appears to work. In a detached
        # runner there is no ambient login, so it falls back to the anonymous
        # token, which cannot create tables in anyone's MyDB -- and because
        # the error check compares bytes to str and is never true, the call
        # still returns 'OK'. The result is a create that silently does
        # nothing, surfacing much later as
        # `relation "mydb.<table>" does not exist` on the first insert.
        #
        # Every other MyDB call (`insert`, `drop`, `rename`, `truncate`,
        # `query`) uses `def_token(token)` and is unaffected. This is a bug in
        # one function, not a pattern.
        schema_csv = "".join(f"{name},{dtype}\n" for name, dtype in schema.items())
        if self._impl is None:
            raise MyDBError(
                "Could not reach the queryClient implementation object; "
                "cannot create tables with an explicit token."
            )
        try:
            raw = self._impl._mydb_create(
                token=self.token,
                table=table,
                schema=schema_csv,
                # drop=True only for a listed-but-unreadable table, which
                # holds nothing recoverable. Never for a readable one.
                drop=bool(listed),
            )
        except Exception as exc:
            raise MyDBError(
                f"Could not create MyDB table {table!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        columns = self.describe(table)
        if sorted(columns) == sorted(schema):
            logger.info(
                "Created MyDB table %r with %d columns%s.",
                table, len(columns),
                " (repaired a phantom entry)" if listed else "",
            )
            return True
        if columns:
            raise MyDBError(
                f"MyDB table {table!r} was created with columns {columns}, "
                f"expected {list(schema)}."
            )
        # Fatal. Letting this slide with a warning only moved the failure to
        # the first insert, with a message that named neither the creation nor
        # its cause.
        raise MyDBError(
            f"Could not create MyDB table {table!r}: not readable after "
            f"creation. Service said {str(raw)[:160]!r} (note: mydb_create "
            f"cannot report errors and always returns 'OK'). Tables listed: "
            f"{self.list_tables()}. Token recognised as an auth token: "
            f"{self._token_looks_valid()}."
        )

    def _token_looks_valid(self) -> bool:
        """Whether ``dl`` parses our token as an auth token.

        Notes
        -----
        Several `queryClient` wrappers decide whether their first positional
        argument is a token or a table name by calling `is_auth_token` on it.
        A token that fails that test is silently reinterpreted as a table
        name, so this is worth reporting when something inexplicable happens.
        """
        try:
            from dl.queryClient import is_auth_token  # noqa: PLC0415

            return bool(is_auth_token(self.token))
        except Exception:
            return False

    def drop(self, table: str) -> None:
        """Drop `table` entirely.

        Warnings
        --------
        Destroys unconsumed rows. Intended for cleaning up a table created
        with a wrong schema, not for routine reclamation -- use
        `delete_below` for that.
        """
        try:
            result = self._qc.mydb_drop(self.token, table)
        except Exception as exc:
            raise MyDBError(f"Could not drop {table!r}: {exc}") from exc
        _check(result, f"dropping {table!r}")
        # Verified rather than trusted: a drop that fails is easy to miss and
        # leaves the next ensure_table skipping creation, so the broken table
        # survives and every insert fails.
        if table in self.list_tables():
            raise MyDBError(
                f"MyDB still reports {table!r} after dropping it "
                f"(service said: {result!r})."
            )

    # -- write (runner side) ----------------------------------------------

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> int:
        """Append `rows` to `table`.

        Parameters
        ----------
        table : str
            Target table.
        rows : list of dict
            Records keyed by the columns of `LOCI_SCHEMA`. Missing keys are
            written as empty, which PostgreSQL reads as NULL.

        Returns
        -------
        int
            Number of rows sent.

        Notes
        -----
        Serialises to CSV in `LOCI_SCHEMA` order, since the service takes CSV
        text. Booleans are emitted as ``t``/``f`` and `None` as an empty
        field, both of which PostgreSQL's CSV input understands.
        """
        if not rows:
            return 0
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(LOCI_SCHEMA.keys())
        for row in rows:
            writer.writerow(
                [_csv_value(row.get(column)) for column in LOCI_SCHEMA]
            )
        payload = buf.getvalue()
        try:
            _check(
                self._qc.mydb_insert(self.token, table, payload),
                f"inserting into {table!r}",
            )
        except Exception as first:
            # The VM rotates this table by renaming it and immediately
            # recreating it. That window is short but not zero, and an insert
            # landing inside it fails because the name momentarily does not
            # exist. Recreate and retry once rather than losing the batch --
            # the runner has already moved its Kafka offsets past these
            # alerts, so a dropped batch is a permanent loss.
            logger.warning(
                "Insert into %r failed (%s); ensuring table and retrying once.",
                table, first,
            )
            try:
                self.ensure_table(table)
                _check(
                    self._qc.mydb_insert(self.token, table, payload),
                    f"inserting into {table!r} (retry)",
                )
            except Exception as second:
                raise MyDBError(
                    f"Could not insert {len(rows)} rows into {table!r} after "
                    f"retry: {second} (first attempt: {first})"
                ) from second
        return len(rows)

    # -- read and reclaim (VM side) ---------------------------------------

    def select_since(
        self, table: str, watermark: float = 0.0, limit: int = 5000
    ) -> list[dict[str, Any]]:
        """Return rows written after `watermark`, oldest first.

        Parameters
        ----------
        table : str
            Source table.
        watermark : float, optional
            Highest `written_at` already consumed.
        limit : int, optional
            Maximum rows per call, so one runaway handler cannot return an
            unbounded batch to the VM.

        Returns
        -------
        list of dict
            Rows as dicts, values left as strings for the caller to coerce.
        """
        sql = (
            f"SELECT * FROM mydb://{table} "  # noqa: S608 -- table is ours, not user input
            f"WHERE written_at > {float(watermark)} "
            f"ORDER BY written_at ASC LIMIT {int(limit)}"
        )
        try:
            raw = self._qc.query(self.token, sql=sql, fmt="csv", timeout=self.timeout)
        except Exception as exc:
            raise MyDBError(f"Could not read {table!r}: {exc}") from exc
        return list(csv.DictReader(io.StringIO(raw or "")))

    def drain_table_name(self, table: str) -> str:
        """Return the name a full table is renamed to for draining."""
        return f"{table}_drain"

    def rotate_for_drain(self, table: str) -> Optional[str]:
        """Set `table` aside for draining and put a fresh one in its place.

        Parameters
        ----------
        table : str
            The table the runner writes to.

        Returns
        -------
        str or None
            The drain table to read and then drop, or `None` if `table` does
            not exist yet.

        Notes
        -----
        Cleanup is rotation, not deletion, because the Data Lab query service
        accepts **only SELECT**. ``DELETE ... WHERE``, ``UPDATE``, and every
        table-name form of them are refused with "The specified query has
        invalid syntax", so there is no way to remove individual rows.

        Rotation is also better than the obvious alternative of truncating
        once a run finishes. Truncate is all-or-nothing and races the runner:
        anything written between the VM's read and the truncate is lost. It
        also has no safe moment in continuous mode, where a job never stops.
        Renaming has no race -- the runner keeps writing to the fresh table
        while the VM drains the old one whenever it likes.

        **Crash-safe.** If a previous cycle died between renaming and
        dropping, the drain table still holds rows nobody has consumed. That
        is detected here and returned for draining *instead of* rotating
        again, so those rows are recovered rather than overwritten.

        The recreate follows the rename immediately, keeping the window in
        which the runner has nowhere to write down to a single call. The
        runner is still expected to retry an insert once via `ensure_table`,
        since that window is not zero.
        """
        drain = self.drain_table_name(table)
        listed = [t.strip() for t in self.list_tables()]

        if drain in listed:
            logger.warning(
                "MyDB drain table %r already exists; an earlier cycle did not "
                "finish. Draining it before rotating again.",
                drain,
            )
            return drain

        if table not in listed:
            return None

        try:
            _check(
                self._qc.mydb_rename(self.token, table, drain),
                f"renaming {table!r} to {drain!r}",
            )
        except MyDBError:
            raise
        except Exception as exc:
            raise MyDBError(f"Could not rename {table!r}: {exc}") from exc

        # Immediately, so the runner's next insert has a target.
        self.ensure_table(table)
        return drain

    def drain(self, drain_table: str, page: int = 5000) -> list[dict[str, Any]]:
        """Read every row from a drain table, oldest first.

        Parameters
        ----------
        drain_table : str
            Table produced by `rotate_for_drain`.
        page : int, optional
            Rows per request.

        Returns
        -------
        list of dict
            All rows, ordered by `written_at`.

        Warnings
        --------
        **Do not trust `subscription_id` or `generation` from these rows.**
        The table lives on the PI's own account, and the runner and its job
        spec are staged in a directory they can write to. A PI could edit
        either and emit rows naming a different subscription, which an
        unquestioning upsert would file under another PI's data.

        The caller already knows whose account it authenticated to, so it
        should use *its own* subscription and compare the row's `generation`
        against the value it holds rather than adopting it. Treat every
        column here as a claim, not a fact.

        Notes
        -----
        Paged on `written_at` rather than OFFSET, which is what that column
        is still for now that it is no longer a delete watermark. Rows with
        an identical `written_at` on a page boundary would be skipped, but
        the runner stamps microseconds and only one runner writes to a
        subscription at a time.
        """
        rows: list[dict[str, Any]] = []
        watermark = 0.0
        while True:
            batch = self.select_since(drain_table, watermark, limit=page)
            if not batch:
                break
            rows.extend(batch)
            try:
                watermark = float(batch[-1]["written_at"])
            except (KeyError, TypeError, ValueError):
                logger.error(
                    "Row in %r has no usable written_at; stopping drain to "
                    "avoid looping.", drain_table
                )
                break
            if len(batch) < page:
                break
        return rows

    def finish_drain(self, drain_table: str) -> None:
        """Drop a drained table.

        Warnings
        --------
        Call **only** after the rows are committed to `AntaresLocus`. The
        runner has already advanced its Kafka offsets past them, so anything
        dropped before ingest is gone for good.
        """
        self.drop(drain_table)

def _parse_schema_listing(raw: Any) -> list[str]:
    """Extract column names from a `mydb_list` schema listing.

    Notes
    -----
    The listing is loosely formatted -- one column per line, name first,
    type after whitespace or a comma -- so this reads the first token of each
    line and ignores anything that does not look like an identifier. Being
    permissive is deliberate: the format is not contractual, and guessing
    wrong here previously produced a confident but empty column list.
    """
    text = str(raw or "").strip()
    lowered = text.lower()
    # The service answers in prose for several non-results ("No tables",
    # "relation ... not known"). Parsed naively those yield a column called
    # "No", which would make an absent table look real.
    if not text or any(
        phrase in lowered
        for phrase in ("error", "no tables", "not known", "not found", "invalid")
    ):
        return []
    columns = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("-") or line.lower().startswith("table"):
            continue
        name = line.replace(",", " ").split()[0].strip('"')
        if name and (name[0].isalpha() or name[0] == "_"):
            columns.append(name)
    return columns


def _check(result: Any, what: str) -> str:
    """Raise if a ``dl`` client call returned an error string.

    Parameters
    ----------
    result : Any
        Whatever the ``dl`` call returned.
    what : str
        Description of the operation, for the error message.

    Returns
    -------
    str
        The result, when it does not look like an error.

    Raises
    ------
    MyDBError
        If the result looks like a failure report.

    Notes
    -----
    The ``dl`` query client reports failure by **returning** an error string,
    not by raising -- e.g. `mydb_drop` ends with::

        if 'error' in str(r.content).lower() or 'not' in str(r.content).lower():
            return qcToString(r.content)
        else:
            return 'OK'

    So wrapping these calls in ``try/except`` catches nothing and a failed
    operation reads as success. Every call must inspect its return value.
    Note also how broad that check is: any response containing "not"
    anywhere is reported as an error, so the message is surfaced verbatim
    rather than interpreted.
    """
    text = str(result or "").strip()
    if text and text.upper() != "OK" and (
        "error" in text.lower() or "not " in text.lower() or "fail" in text.lower()
    ):
        raise MyDBError(f"{what}: {text}")
    return text


def _csv_value(value: Any) -> str:
    """Render `value` for PostgreSQL CSV input."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "t" if value else "f"
    return str(value)
