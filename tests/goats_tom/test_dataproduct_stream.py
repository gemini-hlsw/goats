"""Tests for `DataProductStreamView`, which serves bytes GOATS does not hold.

This view is the only thing standing between a data product's bytes and
anyone who can guess a filename, because a remote storage backend has no
web server in front of it enforcing anything. `FileSystemStorage` had one;
VOSpace does not.
"""

from unittest.mock import patch

import pytest
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import resolve, reverse
from guardian.shortcuts import assign_perm
from tom_dataproducts.models import DataProduct
from tom_targets.tests.factories import SiderealTargetFactory

from goats_tom.tests.factories import UserFactory

NAME = "users/alice/goats/M31/GEM/GS-2026A-Q-1-1/f.fits"


@pytest.fixture
def product(db, tmp_path, settings):
    """A data product whose file really exists under the test storage."""
    settings.MEDIA_ROOT = tmp_path
    target = SiderealTargetFactory.create(name="M31")
    dp = DataProduct.objects.create(target=target, product_id="p1")
    dp.data.name = default_storage.save(NAME, ContentFile(b"FITS-BYTES"))
    dp.save()
    return dp


@pytest.fixture
def owner(db, product):
    """A user who may view `product`."""
    user = UserFactory()
    assign_perm("tom_dataproducts.view_dataproduct", user, product)
    return user


@pytest.mark.django_db
class TestPermissions:
    """Who gets the bytes."""

    def test_owner_receives_the_file(self, client, product, owner):
        client.force_login(owner)
        response = client.get(reverse("dataproduct-stream", kwargs={"name": product.data.name}))
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == b"FITS-BYTES"

    def test_another_user_is_refused(self, client, product):
        """Sharing is per object, and this is where that is enforced."""
        stranger = UserFactory()
        client.force_login(stranger)
        response = client.get(
            reverse("dataproduct-stream", kwargs={"name": product.data.name})
        )
        assert response.status_code in (302, 403)

    def test_superuser_is_refused_without_an_assigned_row(self, client, product):
        """One rule, not two.

        Notes
        -----
        `has_assigned_perm` rather than `has_perm`, so an administrator
        needs an assigned row like anyone else. Every other data product
        path behaves this way; a superuser bypass here would be a hole in
        the one place the bytes are actually handed over.
        """
        admin = UserFactory(is_superuser=True)
        client.force_login(admin)
        response = client.get(
            reverse("dataproduct-stream", kwargs={"name": product.data.name})
        )
        assert response.status_code in (302, 403)

    def test_anonymous_is_refused(self, client, product):
        response = client.get(
            reverse("dataproduct-stream", kwargs={"name": product.data.name})
        )
        assert response.status_code in (302, 403)


@pytest.mark.django_db
class TestMissingThings:
    """What happens when the row or the bytes are not there."""

    def test_unknown_name_is_404(self, client, db):
        user = UserFactory()
        client.force_login(user)
        response = client.get(
            reverse("dataproduct-stream", kwargs={"name": "users/x/goats/nope.fits"})
        )
        assert response.status_code == 404

    def test_unknown_name_does_not_leak_existence(self, client, db):
        """404, not 403.

        Notes
        -----
        A 403 would confirm that a file by that name exists somewhere and
        the caller merely lacks access. A 404 says only that GOATS has no
        record of it.
        """
        user = UserFactory()
        client.force_login(user)
        response = client.get(
            reverse("dataproduct-stream", kwargs={"name": "users/x/goats/nope.fits"})
        )
        assert response.status_code == 404

    def test_missing_bytes_are_404_not_a_crash(self, client, product, owner):
        """A row whose file has gone is a 404, not a 500.

        Notes
        -----
        Reachable if a file was removed out of band, or if a name predates
        the owner prefix `custom_data_product_path` now adds -- in which
        case `VOSpaceStorage._split` raises `SuspiciousFileOperation` rather
        than `FileNotFoundError`, so both are caught.
        """
        client.force_login(owner)
        for error in (FileNotFoundError("gone"), SuspiciousFileOperation("bad name")):
            with patch.object(default_storage, "open", side_effect=error):
                response = client.get(
                    reverse("dataproduct-stream", kwargs={"name": product.data.name})
                )
            assert response.status_code == 404


class TestRouting:
    """The URL has to be the one `VOSpaceStorage.url` hands out."""

    def test_url_resolves_back_to_this_view(self):
        """The backend and the route must agree, so ask the backend.

        Notes
        -----
        `VOSpaceStorage.url` builds this path as a string and nothing else
        forces it to match the URLconf. If they drift, every download link
        in `datalab` mode 404s.
        """
        from goats_tom.astro_data_lab import VOSpaceStorage

        match = resolve(VOSpaceStorage().url(NAME))
        assert match.func.view_class.__name__ == "DataProductStreamView"
        assert match.kwargs["name"] == NAME

    def test_separators_survive_the_route(self):
        """`<path:name>`, not `<str:name>`.

        Notes
        -----
        A storage name contains separators, and `str` stops at the first
        one -- which would hand the view a truncated name that matches no
        data product.
        """
        match = resolve(f"/dataproducts/stream/{NAME}")
        assert match.kwargs["name"] == NAME


@pytest.mark.django_db
class TestStreaming:
    """How the bytes come back."""

    def test_response_streams_rather_than_buffering(self, client, product, owner):
        """FITS files are large enough that this matters.

        Notes
        -----
        A handful of concurrent downloads read fully into memory would take
        the process down. `FileResponse` reads in chunks.
        """
        client.force_login(owner)
        response = client.get(
            reverse("dataproduct-stream", kwargs={"name": product.data.name})
        )
        assert response.streaming is True

    def test_filename_is_the_basename(self, client, product, owner):
        """The browser should not be offered the whole storage path."""
        client.force_login(owner)
        response = client.get(
            reverse("dataproduct-stream", kwargs={"name": product.data.name})
        )
        assert "f.fits" in response["Content-Disposition"]
        assert "users/alice" not in response["Content-Disposition"]
