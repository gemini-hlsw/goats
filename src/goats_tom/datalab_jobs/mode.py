"""Whether work runs on Astro Data Lab or on this host."""

__all__ = ["datalab_mode_enabled"]


def datalab_mode_enabled() -> bool:
    """Whether downloads and reductions should run on Data Lab.

    Returns
    -------
    bool
        True when the configured storage backend is `VOSpaceStorage`.

    Notes
    -----
    **Decided by the storage backend, not a separate flag.** The two cannot
    be allowed to disagree: running a download remotely writes into VOSpace,
    and if `default_storage` is still local the resulting `DataProduct` rows
    point at files this host does not have. A single fact both read is the
    only arrangement where that is impossible.

    This is the same question `goats_tom.utils.utils._datalab_storage_enabled`
    asks for naming, and it is asked the same way for the same reason.

    Off by default. With `GOATS_FILE_STORAGE` unset the backend is
    `FileSystemStorage`, this returns False, and every download and reduction
    runs locally exactly as it always has.
    """
    from django.core.files.storage import default_storage  # noqa: PLC0415

    from goats_tom.astro_data_lab import VOSpaceStorage  # noqa: PLC0415

    backend = getattr(default_storage, "_wrapped", default_storage)
    return isinstance(backend, VOSpaceStorage)
