"""Tests `DownloadState.`"""

from unittest.mock import patch

from goats_tom.realtime import DownloadState


def test_format_bytes():
    """Tests the format_bytes function thoroughly."""
    assert DownloadState.format_bytes(500) == "500 B", "Incorrect format for bytes"
    assert DownloadState.format_bytes(1024) == "1 KB", "Incorrect format for kilobytes"
    assert DownloadState.format_bytes(1536) == "2 KB", "Incorrect format for kilobytes"
    assert (
        DownloadState.format_bytes(1048576) == "1.0 MB"
    ), "Incorrect format for megabytes"
    assert (
        DownloadState.format_bytes(1572864) == "1.5 MB"
    ), "Incorrect format for megabytes"
    assert (
        DownloadState.format_bytes(1073741824) == "1.00 GB"
    ), "Incorrect format for gigabytes"
    assert (
        DownloadState.format_bytes(1099511627776) == "1.000 TB"
    ), "Incorrect format for terabytes"
    assert DownloadState.format_bytes(None) == "", "Incorrect format for None"


def test_download_state_complete():
    """Tests a complete download scenario with edge cases."""
    with patch.object(DownloadState, "_send") as mock_send:
        download_state = DownloadState()

        # Send initial updates
        download_state.update_and_send(
            label="File Download",
            status="Started",
            downloaded_bytes=1024,
            message="Download started",
            done=False,
            error=False,
        )
        # Verify that _send was called with the correct parameters.
        mock_send.assert_called_with()
        assert (
            download_state.label == "File Download"
        ), "Label not set correctly for initial update"
        assert (
            download_state.status == "Started"
        ), "Status not set correctly for initial update"
        assert (
            download_state.downloaded_bytes == 1024
        ), "Downloaded bytes not set correctly for initial update"
        assert (
            download_state.message == "Download started"
        ), "Message not set correctly for initial update"
        assert not download_state.done, "Done flag should be False for initial update"
        assert not download_state.error, "Error flag should be False for initial update"

        # Update the download state to in-progress.
        download_state.update_and_send(
            downloaded_bytes=2048, message="Download in progress", status="In Progress",
        )

        # Verify that _send was called again with the updated parameters.
        mock_send.assert_called_with()
        assert (
            download_state.label == "File Download"
        ), "Label should persist during update"
        assert download_state.status == "In Progress", "Status not updated correctly"
        assert (
            download_state.downloaded_bytes == 2048
        ), "Downloaded bytes not updated correctly"
        assert (
            download_state.message == "Download in progress"
        ), "Message not updated correctly"
        assert not download_state.done, "Done flag should be False during update"
        assert not download_state.error, "Error flag should be False during update"

        # Complete the download.
        download_state.update_and_send(
            downloaded_bytes=4096, message="Download complete", done=True,
        )

        # Verify that _send was called again with the completion parameters.
        mock_send.assert_called_with()
        assert (
            download_state.label == "File Download"
        ), "Label should persist during completion"
        assert (
            download_state.status == "In Progress"
        ), "Status should persist during completion"
        assert (
            download_state.downloaded_bytes == 4096
        ), "Downloaded bytes not updated correctly during completion"
        assert (
            download_state.message == "Download complete"
        ), "Message not updated correctly during completion"
        assert download_state.done, "Done flag should be True during completion"
        assert not download_state.error, "Error flag should be False during completion"
