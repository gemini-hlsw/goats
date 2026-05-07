"""
Upload GPP finder chart attachment in background.
"""

__all__ = ["upload_finder_chart"]

from pathlib import Path

import dramatiq
from asgiref.sync import async_to_sync
from django.conf import settings
from gpp_client import GPPClient
from gpp_client.api.enums import AttachmentType
from gpp_client.exceptions import GPPResponseError

from goats_tom.models import GPPLogin
from goats_tom.realtime import NotificationInstance


def _error(
    upload_id: str,
    message: str,
    *,
    label: str = "Finder chart upload",
    notify: bool = True,
) -> dict:
    if notify:
        NotificationInstance.create_and_send(
            label=label,
            message=message,
            color="danger",
        )
    return {"state": "ERROR", "upload_id": upload_id, "message": message}


@dramatiq.actor(
    max_retries=0,
    time_limit=getattr(settings, "DRAMATIQ_ACTOR_TIME_LIMIT", 86400000),
)
def upload_finder_chart(
    *,
    upload_id: str,
    tmp_path: str,
    file_name: str,
    program_id: str,
    observation_id: str,
    description: str,
    user_id: int,
) -> dict:
    """
    Upload a finder chart to GPP and attach it to an observation.
    """
    path = Path(tmp_path)

    try:
        if not path.is_file():
            return _error(
                upload_id,
                "Temporary file not found.",
                label="Finder chart upload",
            )

        content_bytes = path.read_bytes()

        try:
            credentials = GPPLogin.objects.get(user_id=user_id)
        except Exception:
            return _error(
                upload_id,
                "GPP credentials not found for this user.",
                label="GPP authentication",
            )

        token = getattr(credentials, "token", None)
        if not token:
            return _error(
                upload_id,
                "Missing GPP token.",
                label="GPP authentication",
            )

        attachment_type = AttachmentType("FINDER")

        async def _execute_gpp_workflow() -> dict:
            client = GPPClient(env=settings.GPP_ENV, token=token)
            try:
                upload_result = await client.attachment.upload(
                    program_id=program_id,
                    attachment_type=attachment_type,
                    file_name=file_name,
                    description=description,
                    content=content_bytes,
                )

                new_id = (
                    upload_result.get("id")
                    if isinstance(upload_result, dict)
                    else upload_result
                )
                if not new_id:
                    return _error(
                        upload_id,
                        "GPP did not return attachment id.",
                        label="Finder chart upload",
                        notify=False,
                    )

                attachments_data = await client.attachment.get_all_by_observation(
                    observation_id=observation_id,
                    observation_reference=None,
                )

                existing_ids = []
                if isinstance(attachments_data, dict):
                    attachments = attachments_data.get("attachments")
                    if isinstance(attachments, list):
                        for a in attachments:
                            if isinstance(a, dict) and a.get("id"):
                                existing_ids.append(str(a["id"]))

                combined_ids = list(dict.fromkeys(existing_ids + [str(new_id)]))

                await client.observation.update_by_id(
                    observation_id=observation_id,
                    from_json={"attachments": combined_ids},
                )

                return {"state": "DONE", "id": str(new_id), "upload_id": upload_id}

            finally:
                try:
                    await client.close()
                except Exception:
                    pass

        try:
            result = async_to_sync(_execute_gpp_workflow)()

        except GPPResponseError as exc:
            msg = str(exc)
            if "Duplicate file name" in msg:
                msg = (
                    f"A file named '{file_name}' already exists in GPP. "
                    "Please rename it or remove the existing file."
                )
            return _error(
                upload_id,
                msg,
                label="Finder chart upload",
            )

        # If workflow returned ERROR, notify (matches your previous behavior)
        if isinstance(result, dict) and result.get("state") == "ERROR":
            NotificationInstance.create_and_send(
                label="Finder chart upload",
                message=result.get("message", "Upload failed."),
                color="danger",
            )

        return result

    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
