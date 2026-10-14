import importlib
import logging
import os
import threading
import time
from unittest import mock

import pytest

# The package re-exports the actor under the module's name.
task = importlib.import_module("goats_tom.tasks.run_dragons_reduce")

DRAGONS_LOGGER = logging.getLogger("geminidr")


class CapturingHandler(logging.Handler):
    """Stands in for `DRAGONSHandler`, keeping what it would send to the browser."""

    instances: list["CapturingHandler"] = []

    def __init__(self, **kwargs):
        super().__init__()
        self.messages: list[str] = []
        CapturingHandler.instances.append(self)

    def emit(self, record):
        self.messages.append(record.getMessage())


def make_reduce(output_dir):
    reduce = mock.MagicMock()
    reduce.recipe.dragons_run.get_output_dir.return_value = output_dir
    reduce.recipe.dragons_run.log_filename = str(output_dir / "log.log")
    reduce.recipe.active_function_definition = "def recipe(p):\n    pass\n"
    reduce.recipe.uparms = None
    reduce.recipe.ucals = None
    reduce.recipe.additional_files = None
    return reduce


@pytest.fixture
def patched(tmp_path):
    """Run the task without DRAGONS, the database or the channel layer."""
    CapturingHandler.instances = []
    reduces = {}

    def get(id):
        return reduces[id]

    with (
        mock.patch.object(task.DRAGONSReduce.objects, "get", side_effect=get),
        mock.patch.object(task.DRAGONSFile.objects, "filter", return_value=[]),
        mock.patch.object(task, "DRAGONSHandler", CapturingHandler),
        mock.patch.object(task, "NotificationInstance"),
        mock.patch.object(task, "DRAGONSProgress"),
        mock.patch.object(task.time, "sleep"),
        mock.patch.object(task, "Reduce") as reduce_cls,
    ):
        yield reduces, reduce_cls


def test_worker_logging_and_cwd_survive_a_reduction(tmp_path, patched):
    reduces, _ = patched
    reduces[1] = make_reduce(tmp_path)
    root = logging.getLogger()
    worker_handler = logging.NullHandler()
    root.addHandler(worker_handler)
    cwd = os.getcwd()
    try:
        handlers_before = list(root.handlers)

        task.run_dragons_reduce.fn(1, [])

        assert root.handlers == handlers_before
        assert os.getcwd() == cwd
    finally:
        root.removeHandler(worker_handler)


def test_other_threads_do_not_reach_the_reduction_log(tmp_path, patched):
    reduces, reduce_cls = patched
    reduces[1] = make_reduce(tmp_path)

    def runr():
        foreign = threading.Thread(
            target=DRAGONS_LOGGER.warning, args=("from another task",)
        )
        foreign.start()
        foreign.join()
        DRAGONS_LOGGER.warning("from the reduction")

    reduce_cls.return_value.runr.side_effect = runr

    task.run_dragons_reduce.fn(1, [])

    assert CapturingHandler.instances[0].messages == ["from the reduction"]
    assert "from another task" not in (tmp_path / "log.log").read_text()


def test_concurrent_reductions_take_turns(tmp_path, patched):
    reduces, reduce_cls = patched
    spans = {}
    for pk in (1, 2):
        output_dir = tmp_path / str(pk)
        output_dir.mkdir()
        reduces[pk] = make_reduce(output_dir)

    def runr():
        name = os.path.basename(os.getcwd())
        start = time.monotonic()
        DRAGONS_LOGGER.warning(f"reduction {name}")
        threading.Event().wait(0.2)
        assert os.path.basename(os.getcwd()) == name
        spans[name] = (start, time.monotonic())

    reduce_cls.return_value.runr.side_effect = runr

    threads = [
        threading.Thread(target=task.run_dragons_reduce.fn, args=(pk, []))
        for pk in (1, 2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    (start_a, end_a), (start_b, end_b) = sorted(spans.values())
    assert end_a <= start_b
    assert sorted(len(h.messages) for h in CapturingHandler.instances) == [1, 1]
