import types
import pytest
import dramatiq
from apscheduler.triggers.cron import CronTrigger

MODULE = "goats_scheduler.scheduling.cron"


@pytest.fixture(autouse=True)
def clean_registry():
    """
    Ensure SCHEDULED_JOBS starts empty for each test.
    """
    mod = __import__(MODULE, fromlist=["*"])
    mod.SCHEDULED_JOBS.clear()
    yield
    mod.SCHEDULED_JOBS.clear()


@pytest.fixture
def mod():
    """Import the module under test."""
    return __import__(MODULE, fromlist=["*"])


def test_registers_actor_and_builds_job_dict(mod):
    @mod.cron(minute="*", hour="*", coalesce=False, max_instances=2, replace_existing=False)
    @dramatiq.actor
    def ping():
        pass

    assert len(mod.SCHEDULED_JOBS) == 1
    job = mod.SCHEDULED_JOBS[0]

    # basic fields
    assert job["name"] == "ping"
    assert isinstance(job["trigger"], CronTrigger)
    assert job["coalesce"] is False
    assert job["max_instances"] == 2
    assert job["replace_existing"] is False

    assert job["module_func"].endswith(":ping")
    assert job["job_path"].endswith(":ping.send")


def test_multiple_registrations_accumulate(mod):
    @mod.cron(minute="0")
    @dramatiq.actor
    def a():
        pass

    @mod.cron(hour="*")
    @dramatiq.actor
    def b():
        pass

    names = {j["name"] for j in mod.SCHEDULED_JOBS}
    assert names == {"a", "b"}
    assert all(isinstance(j["trigger"], CronTrigger) for j in mod.SCHEDULED_JOBS)


def test_raises_if_not_dramatiq_actor(mod):
    with pytest.raises(TypeError) as exc:
        @mod.cron(minute="*")
        def not_actor():
            pass
    assert "dramatiq.Actor" in str(exc.value)


def test_cron_kwargs_passed_to_crontrigger(mod):
    @mod.cron(minute="*/5", day_of_week="mon-fri")
    @dramatiq.actor
    def task():
        pass

    job = mod.SCHEDULED_JOBS[0]
    assert isinstance(job["trigger"], CronTrigger)


def test_module_func_and_job_path_include_module_and_send(mod):
    @mod.cron(hour="1")
    @dramatiq.actor
    def hello():
        pass

    job = mod.SCHEDULED_JOBS[0]
    assert job["module_func"].endswith(":hello")
    assert job["job_path"].endswith(":hello.send")
