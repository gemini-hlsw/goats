import pytest

MODULE = "goats_scheduler.management.commands.run_scheduler"


@pytest.fixture
def mod():
    """Import the command module under test."""
    return __import__(MODULE, fromlist=["*"])


class DummyScheduler:
    """Non-blocking fake scheduler to assert interactions."""
    def __init__(self):
        self.added = []
        self.started = False
        self.shutdown_called = False
        self.shutdown_kwargs = None

    def add_job(self, func, *, trigger, name, coalesce, max_instances, replace_existing):
        self.added.append(dict(
            func=func,
            trigger=trigger,
            name=name,
            coalesce=coalesce,
            max_instances=max_instances,
            replace_existing=replace_existing,
        ))

    def start(self):
        self.started = True

    def shutdown(self, **kwargs):
        self.shutdown_called = True
        self.shutdown_kwargs = kwargs


def test_no_jobs_prints_notice_and_starts(monkeypatch, capsys, mod):
    """When SCHEDULED_JOBS is empty, it should print a notice and still start."""
    dummy = DummyScheduler()
    monkeypatch.setattr(mod, "BlockingScheduler", lambda: dummy)
    monkeypatch.setattr(mod.signal, "signal", lambda *a, **k: None)
    monkeypatch.setattr(mod, "SCHEDULED_JOBS", [], raising=True)

    mod.Command().handle()

    out = capsys.readouterr().out
    assert "* No scheduled jobs found." in out
    assert "* Running Task Scheduler" in out
    assert dummy.started is True
    assert dummy.added == []


def test_registers_jobs_and_prints_discovery(monkeypatch, capsys, mod):
    """It should register every job from the registry and print discovery lines."""
    dummy = DummyScheduler()
    monkeypatch.setattr(mod, "BlockingScheduler", lambda: dummy)
    monkeypatch.setattr(mod.signal, "signal", lambda *a, **k: None)

    jobs = [
        {
            "module_func": "goats_tom.tasks.check_version",
            "job_path": lambda: None,
            "trigger": object(),
            "name": "check_version",
            "coalesce": True,
            "max_instances": 1,
            "replace_existing": True,
        },
        {
            "module_func": "foo.bar.baz",
            "job_path": lambda: None,
            "trigger": object(),
            "name": "baz",
            "coalesce": False,
            "max_instances": 2,
            "replace_existing": False,
        },
    ]
    monkeypatch.setattr(mod, "SCHEDULED_JOBS", jobs, raising=True)

    mod.Command().handle()

    out = capsys.readouterr().out
    assert "* Discovered tasks module: 'goats_tom.tasks.check_version'" in out
    assert "* Discovered tasks module: 'foo.bar.baz'" in out
    assert "* Running Task Scheduler" in out

    assert len(dummy.added) == 2
    for added, job in zip(dummy.added, jobs):
        assert added["func"] is job["job_path"]
        assert added["trigger"] is job["trigger"]
        assert added["name"] == job["name"]
        assert added["coalesce"] == job["coalesce"]
        assert added["max_instances"] == job["max_instances"]
        assert added["replace_existing"] == job["replace_existing"]


def test_signal_handler_shutdown_and_exit(monkeypatch, mod):
    """Signal handler must call shutdown(wait=False) and sys.exit(0)."""
    dummy = DummyScheduler()
    monkeypatch.setattr(mod, "BlockingScheduler", lambda: dummy)

    handlers = []
    monkeypatch.setattr(mod.signal, "signal", lambda _sig, h: handlers.append(h))

    exit_code = {"code": None}

    def fake_exit(code):
        exit_code["code"] = code
        raise SystemExit(code)

    monkeypatch.setattr(mod.sys, "exit", fake_exit)
    monkeypatch.setattr(mod, "SCHEDULED_JOBS", [], raising=True)

    mod.Command().handle()
    assert handlers, "No signal handlers registered"

    handler = handlers[0]
    with pytest.raises(SystemExit) as exc:
        handler(None, None)

    assert dummy.shutdown_called is True
    assert dummy.shutdown_kwargs == {"wait": False}
    assert exit_code["code"] == 0
    assert exc.value.code == 0
def test_disables_logger_propagation(monkeypatch, mod):
    names = (
        "apscheduler",
        "apscheduler.scheduler",
        "apscheduler.executors.default",
        "apscheduler.jobstores.default",
        "apscheduler.triggers",
    )
    # Save current state
    original = {n: mod.logging.getLogger(n).propagate for n in names}
    try:
        dummy = DummyScheduler()
        monkeypatch.setattr(mod, "BlockingScheduler", lambda: dummy)
        monkeypatch.setattr(mod.signal, "signal", lambda *a, **k: None)
        monkeypatch.setattr(mod, "SCHEDULED_JOBS", [], raising=True)

        mod.Command().handle()

        assert all(mod.logging.getLogger(n).propagate is False for n in names)
    finally:
        # Restore to avoid contaminating pytest's logging
        for n, p in original.items():
            mod.logging.getLogger(n).propagate = p
