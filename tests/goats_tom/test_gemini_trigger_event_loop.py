"""Regression tests for the event loop the Gemini trigger runs its calls in.

Every other test in `test_gemini_trigger.py` replaces the GPP client with a
mock, which is why none of them caught the bug these cover: a mock is happy to
be called from any event loop, so the guards all passed while triggering
failed in production on every single attempt with ``Event loop is closed``.

The fake client here is deliberately stricter than a mock and models the one
behaviour that matters -- an httpx connection pool binds to the event loop
that first uses it, and is unusable from any other. That is enough to tell a
single shared loop apart from one loop per call.
"""

import asyncio

import pytest
from django.contrib.auth.models import User
from tom_targets.models import Target

from goats_tom.gemini_trigger import trigger_gemini_observation
from goats_tom.models import (
    AntaresStreamSubscription,
    GeminiTriggerRecord,
    GPPLogin,
)


@pytest.fixture()
def owner(db):
    """A PI with GPP credentials stored."""
    user = User.objects.create_user("looppi")
    GPPLogin.objects.create(user=user, token="tok")
    return user


@pytest.fixture()
def subscription(owner):
    """A subscription configured to trigger, with a template."""
    return AntaresStreamSubscription.objects.create(
        owner=owner,
        topics=["t"],
        trigger_gemini_observations=True,
        gpp_program_id="p-1",
        gpp_observation_id="o-1",
        max_triggers=10,
    )


@pytest.fixture()
def target(db):
    """A saved target to point the observation at."""
    return Target.objects.create(
        name="ANT2026loop", type=Target.SIDEREAL, ra=10.0, dec=20.0
    )


class _Payload:
    """Stands in for a gpp_client response model."""

    def __init__(self, data):
        self._data = data

    def model_dump(self, by_alias=False):
        return self._data


class _LoopBoundClient:
    """A fake GPP client that refuses to work across event loops.

    Notes
    -----
    The real client holds an `httpx.AsyncClient` whose connection pool binds to
    whichever loop first drives it. `asyncio.run` and `async_to_sync` both close
    their loop on return, so a second call on a new loop finds the pool bound to
    a dead one and raises ``RuntimeError: Event loop is closed``. Reproduced
    here by recording the loop on first use and rejecting any other.
    """

    def __init__(self, token=None):
        self.token = token
        self._loop = None
        self.calls = []
        self.closed = False
        self.goats = _Namespace(
            get_observations_by_program_id=self._make("observations")
        )
        self.target = _Namespace(create_by_program_id=self._make("create_target"))
        self.observation = _Namespace(clone=self._make("clone"))
        self.workflow_state = _Namespace(
            update_by_id_with_retry=self._make("workflow")
        )

    def _bind(self):
        current = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = current
        elif self._loop is not current or self._loop.is_closed():
            raise RuntimeError("Event loop is closed")

    def _make(self, name):
        async def _call(**kwargs):
            self._bind()
            self.calls.append(name)
            return _RESPONSES[name]

        return _call

    async def close(self):
        self._bind()
        self.closed = True


class _Namespace:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


_RESPONSES = {
    "observations": _Payload(
        {
            "observations": {
                "matches": [
                    {
                        "id": "o-1",
                        "scienceBand": "BAND1",
                        "program": {
                            "allocations": [
                                {
                                    "scienceBand": "BAND1",
                                    "duration": {"hours": 10.0},
                                }
                            ],
                            "timeCharge": [
                                {"band": "BAND1", "time": {"program": {"hours": 1.0}}}
                            ],
                        },
                    }
                ]
            }
        }
    ),
    "create_target": _Payload({"createTarget": {"target": {"id": "t-new"}}}),
    "clone": _Payload({"cloneObservation": {"newObservation": {"id": "o-new"}}}),
    "workflow": "READY",
}


@pytest.mark.django_db()
class TestSingleEventLoop:
    """All GPP calls for one attempt share one loop."""

    def test_trigger_succeeds_against_a_loop_bound_client(
        self, subscription, target, monkeypatch
    ):
        """The regression test for ``Event loop is closed``.

        Fails against the previous implementation, which wrapped each GPP call
        in its own `async_to_sync` and so hit a dead loop on the second one.
        """
        import gpp_client

        created = {}

        def _factory(token=None):
            client = _LoopBoundClient(token=token)
            created["client"] = client
            return client

        monkeypatch.setattr(gpp_client, "GPPClient", _factory)

        record = trigger_gemini_observation(subscription, target.name, target)

        assert record.status == GeminiTriggerRecord.STATUS_SUCCESS, record.detail
        assert record.gpp_observation_id == "o-new"
        assert record.gpp_target_id == "t-new"

    def test_every_call_ran_on_one_loop_and_the_client_was_closed(
        self, subscription, target, monkeypatch
    ):
        """The allocation read, the clone and the close all share a loop.

        Asserted on the client rather than inferred from the outcome: a future
        change could reintroduce a second loop somewhere that happens not to
        fail the happy path, and the leak would go unnoticed until a real
        connection pool was on the other end.
        """
        import gpp_client

        created = {}

        def _factory(token=None):
            client = _LoopBoundClient(token=token)
            created["client"] = client
            return client

        monkeypatch.setattr(gpp_client, "GPPClient", _factory)

        trigger_gemini_observation(subscription, target.name, target)

        client = created["client"]
        assert client.calls == [
            "observations",
            "create_target",
            "clone",
            "workflow",
        ]
        assert client.closed, "the client must be closed inside its own loop"

    def test_the_client_is_closed_even_when_the_clone_fails(
        self, subscription, target, monkeypatch
    ):
        """A leaked connection pool per failed alert would accumulate."""
        import gpp_client

        created = {}

        def _factory(token=None):
            client = _LoopBoundClient(token=token)

            async def _boom(**kwargs):
                client._bind()
                raise RuntimeError("boom")

            client.observation.clone = _boom
            created["client"] = client
            return client

        monkeypatch.setattr(gpp_client, "GPPClient", _factory)

        record = trigger_gemini_observation(subscription, target.name, target)

        assert record.status == GeminiTriggerRecord.STATUS_FAILED
        assert created["client"].closed

    def test_allocation_retries_stay_on_the_same_loop(
        self, subscription, target, monkeypatch
    ):
        """A transient read error must not poison the loop for later calls.

        The retry used to run through a fresh `async_to_sync`, so attempts two
        and three could only ever raise ``Event loop is closed`` -- masking the
        real error with a misleading one.
        """
        import gpp_client

        created = {}

        def _factory(token=None):
            client = _LoopBoundClient(token=token)
            attempts = {"n": 0}
            original = client.goats.get_observations_by_program_id

            async def _flaky(**kwargs):
                client._bind()
                attempts["n"] += 1
                if attempts["n"] == 1:
                    raise RuntimeError("transient network blip")
                return await original(**kwargs)

            client.goats.get_observations_by_program_id = _flaky
            created["client"] = client
            created["attempts"] = attempts
            return client

        monkeypatch.setattr(gpp_client, "GPPClient", _factory)

        record = trigger_gemini_observation(subscription, target.name, target)

        assert created["attempts"]["n"] == 2
        assert record.status == GeminiTriggerRecord.STATUS_SUCCESS, record.detail


@pytest.mark.django_db()
class TestTargetCreationPayload:
    """What GOATS actually sends to GPP when creating the target."""

    def _capture(self, monkeypatch):
        import gpp_client

        seen = {}
        client = _LoopBoundClient(token="tok")
        original = client.target.create_by_program_id

        async def _record(**kwargs):
            seen.update(kwargs)
            return await original(**kwargs)

        client.target.create_by_program_id = _record
        monkeypatch.setattr(gpp_client, "GPPClient", lambda token=None: client)
        return seen

    def test_the_epoch_is_sent(self, subscription, target, monkeypatch):
        """GPP refuses a sidereal target without it.

        The schema marks epoch optional, so nothing fails until GPP itself
        rejects the creation with ``Argument 'input.SET.sidereal' is invalid:
        RA, Dec, and Epoch must all be specified on target creation``. The
        mocked tests could not see this -- only a payload assertion can.
        """
        seen = self._capture(monkeypatch)

        trigger_gemini_observation(subscription, target.name, target)

        sidereal = seen["properties"].sidereal
        assert sidereal.epoch == "J2000.000"
        assert sidereal.ra is not None
        assert sidereal.dec is not None


@pytest.mark.django_db()
class TestFailureDetailPunctuation:
    """The message is read by a PI on the dashboard, so it has to read well."""

    def test_no_doubled_full_stop(self, subscription, target, monkeypatch):
        """GPP's own messages already end in a full stop."""
        import gpp_client

        client = _LoopBoundClient(token="tok")

        async def _reject(**kwargs):
            client._bind()
            raise RuntimeError(
                "Argument 'input.SET.sidereal' is invalid: RA, Dec, and Epoch "
                "must all be specified on target creation."
            )

        client.target.create_by_program_id = _reject
        monkeypatch.setattr(gpp_client, "GPPClient", lambda token=None: client)

        record = trigger_gemini_observation(subscription, target.name, target)

        assert ".." not in record.detail
        assert record.detail.endswith("Nothing was created in GPP.")
