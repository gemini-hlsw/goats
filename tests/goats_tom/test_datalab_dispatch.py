"""Tests that downloads and reductions go to the right place.

Two paths now exist for each: local background task, or a job on the PI's
Data Lab account. Which one runs is decided by the storage backend.

The local assertions matter as much as the remote ones. A desktop install
must keep behaving exactly as it does today, and the way that breaks is not
a crash -- it is a download quietly running on Data Lab for someone who
never enabled it.
"""

from unittest.mock import MagicMock, patch

import pytest

from goats_tom.datalab_jobs import datalab_mode_enabled


class TestModeDetection:
    """Which mode is in force, and what decides it."""

    def test_defaults_to_local(self):
        """Desktop must not opt in by accident."""
        assert datalab_mode_enabled() is False

    def test_agrees_with_the_naming_helper(self):
        """Both read the storage backend, so they cannot disagree.

        Notes
        -----
        They answer different questions -- where a file's *name* says it
        lives, and where the *work* runs -- and the two must never diverge.
        A download running remotely while names are built locally produces
        `DataProduct` rows pointing at files this host does not have, and
        nothing reports it.
        """
        from goats_tom.utils.utils import _datalab_storage_enabled

        assert datalab_mode_enabled() == _datalab_storage_enabled()


@pytest.mark.django_db
class TestDownloadDispatch:
    """`GOAQueryFormView` picks a path.

    Notes
    -----
    The local branch is covered by `views/test_goa_query_form.py`, which
    drives the view through a real request. Asserting it here with mocks
    that the branch never reaches would look like coverage and prove
    nothing.
    """

    def test_launcher_builds_the_url_from_the_same_helper(self):
        """Both modes must ask GOA for the same files.

        Notes
        -----
        The local task calls `url_helper.get_tar_file_url` with the form's
        `query_params`. Building the URL any other way here would let the
        two modes return different data for the same form, with nothing
        reporting that they had.
        """
        from goats_tom.views.goa_query_form import GOAQueryFormView

        view = GOAQueryFormView()
        request = MagicMock()
        record = MagicMock()
        query_params = {"args": ("GS-2026A-Q-1",), "kwargs": {"progid": "X"}}

        with patch("goats_tom.views.goa_query_form.GOA") as goa, patch(
            "goats_tom.views.goa_query_form.DataLabJobLauncher"
        ) as launcher_cls:
            goa.url_helper.get_tar_file_url.return_value = "https://archive/x"
            view._launch_on_datalab(request, record, query_params)

        goa.url_helper.get_tar_file_url.assert_called_once_with(
            "GS-2026A-Q-1", progid="X"
        )
        launcher_cls.return_value.launch_download.assert_called_once()
        assert (
            launcher_cls.return_value.launch_download.call_args[0][1]
            == "https://archive/x"
        )


@pytest.mark.django_db
class TestReductionDispatch:
    """`DRAGONSReduceViewSet` picks a path."""

    def test_input_paths_point_at_the_vospace_mount(self):
        """Storage names become notebook-server paths.

        Notes
        -----
        `Reduce.files` takes filesystem paths and the read-only
        `~/vospace/` mount is where a PI's VOSpace appears inside the
        notebook server. This is the one place the two namespaces meet;
        getting it wrong yields a reduction that starts and then reports
        every input missing.
        """
        from goats_tom.api_views.dragons_reduce import DRAGONSReduceViewSet

        view = DRAGONSReduceViewSet()
        reduce = MagicMock()
        recipe = reduce.recipe
        recipe.uparms = None
        recipe.observation_type = "OBJECT"

        file_a = MagicMock()
        file_a.observation_type = "OBJECT"
        file_a.data_product.data.name = "users/alice/goats/M31/GEM/obs/a.fits"

        with patch(
            "goats_tom.api_views.dragons_reduce.DRAGONSFile"
        ) as dragons_file, patch(
            "goats_tom.api_views.dragons_reduce.DataLabJobLauncher"
        ) as launcher_cls:
            dragons_file.objects.filter.return_value = [file_a]
            view._launch_on_datalab(reduce, [1])

        kwargs = launcher_cls.return_value.launch_reduction.call_args.kwargs
        assert kwargs["input_paths"] == [
            "~/vospace/users/alice/goats/M31/GEM/obs/a.fits"
        ]

    def test_recipe_observation_type_is_ordered_first(self):
        """DRAGONS reads tags from the first file.

        Notes
        -----
        Carried over from the local task, where a mismatch crashes recipes
        such as `makeLampFlat` on F2. The two modes must order inputs
        identically or a recipe that works locally fails remotely for a
        reason nothing explains.
        """
        from goats_tom.api_views.dragons_reduce import DRAGONSReduceViewSet

        view = DRAGONSReduceViewSet()
        reduce = MagicMock()
        reduce.recipe.uparms = None
        reduce.recipe.observation_type = "FLAT"

        wrong = MagicMock()
        wrong.observation_type = "OBJECT"
        wrong.data_product.data.name = "users/alice/goats/o.fits"
        right = MagicMock()
        right.observation_type = "FLAT"
        right.data_product.data.name = "users/alice/goats/f.fits"

        with patch(
            "goats_tom.api_views.dragons_reduce.DRAGONSFile"
        ) as dragons_file, patch(
            "goats_tom.api_views.dragons_reduce.DataLabJobLauncher"
        ) as launcher_cls:
            dragons_file.objects.filter.return_value = [wrong, right]
            view._launch_on_datalab(reduce, [1, 2])

        paths = launcher_cls.return_value.launch_reduction.call_args.kwargs[
            "input_paths"
        ]
        assert paths[0].endswith("f.fits")

    def test_a_launch_failure_marks_the_reduction_errored(self):
        """The row already exists, so the PI must see why it stopped.

        Notes
        -----
        `perform_create` has committed by the time this runs. Raising would
        leave a reduction sitting queued forever with a request that looked
        like it succeeded.
        """
        from goats_tom.api_views.dragons_reduce import DRAGONSReduceViewSet

        view = DRAGONSReduceViewSet()
        reduce = MagicMock()
        reduce.recipe.uparms = None

        with patch("goats_tom.api_views.dragons_reduce.DRAGONSFile") as dragons_file, \
            patch(
                "goats_tom.api_views.dragons_reduce.DataLabJobLauncher",
                side_effect=RuntimeError("no account"),
            ), patch("goats_tom.api_views.dragons_reduce.DRAGONSProgress"):
            dragons_file.objects.filter.return_value = []
            view._launch_on_datalab(reduce, [])

        reduce.mark_error.assert_called_once()
