from django.test import TestCase
from django.urls import reverse

from goats_tom.tests.factories import (
    DownloadFactory,
)


class TestRecentDownloadsView(TestCase):
    def test_recent_downloads(self):
        # Create completed Download instances using the factory.
        completed_download = DownloadFactory(done=True)

        # Create incomplete Download instances for control.
        incomplete_download = DownloadFactory(done=False)

        # Use reverse to get the URL.
        url = reverse("recent_downloads")

        # Make a GET request to the view.
        response = self.client.get(url)

        # Get the tasks from the context of the response.
        downloads_in_context = list(response.context["downloads"])

        # Assertions
        self.assertTrue(all(download.done for download in downloads_in_context))
        self.assertIn(completed_download, downloads_in_context)
        self.assertNotIn(incomplete_download, downloads_in_context)
