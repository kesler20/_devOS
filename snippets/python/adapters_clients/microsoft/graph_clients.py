from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class MicrosoftGraphConfig:
    """Configuration for Microsoft Graph clients.

    Parameters
    ----------
    graph_url
        Microsoft Graph base URL.
    default_timezone
        Timezone used for calendar and To Do datetime payloads.
    """

    graph_url: str = "https://graph.microsoft.com/v1.0"
    default_timezone: str = "GMT Standard Time"


class MicrosoftGraphClient:
    """Base Microsoft Graph client with injected HTTP and authentication.

    Parameters
    ----------
    http_client
        Requests-like client with ``get``, ``post``, ``patch``, and ``delete``.
    access_token_provider
        Callable returning a valid Microsoft Graph access token.
    config
        Graph client configuration.
    """

    def __init__(
        self,
        http_client: Any,
        access_token_provider: Callable[[], str],
        config: MicrosoftGraphConfig | None = None,
    ) -> None:
        self._http_client = http_client
        self._access_token_provider = access_token_provider
        self._config = config or MicrosoftGraphConfig()

    def _headers(self, include_content_type: bool = True) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._access_token_provider()}"}
        if include_content_type:
            headers["Content-Type"] = "application/json"
        return headers

    def _raise_for_status(self, response: Any) -> None:
        response.raise_for_status()


class MicrosoftToDoClient(MicrosoftGraphClient):
    """Client for Microsoft To Do via Microsoft Graph."""

    def get_lists(self) -> dict[str, Any]:
        """Read To Do lists.

        Returns
        -------
        dict[str, Any]
            Microsoft Graph list response.
        """

        response = self._http_client.get(
            f"{self._config.graph_url}/me/todo/lists",
            headers=self._headers(include_content_type=False),
        )
        self._raise_for_status(response)
        return dict(response.json())

    def get_list_id_by_name(self, list_name: str) -> str | None:
        """Find a To Do list ID by display name.

        Parameters
        ----------
        list_name
            To Do list display name.

        Returns
        -------
        str | None
            List ID, or ``None``.
        """

        for item in self.get_lists().get("value", []):
            if item.get("displayName") == list_name:
                return item.get("id")
        return None

    def create_task_list(self, list_name: str) -> dict[str, Any]:
        """Create a To Do list.

        Parameters
        ----------
        list_name
            Display name for the new list.

        Returns
        -------
        dict[str, Any]
            Created list response.
        """

        response = self._http_client.post(
            f"{self._config.graph_url}/me/todo/lists",
            headers=self._headers(),
            json={"displayName": list_name},
        )
        self._raise_for_status(response)
        return dict(response.json())

    def get_tasks(self, list_id: str) -> list[dict[str, Any]]:
        """Read tasks from a To Do list.

        Parameters
        ----------
        list_id
            To Do list ID.

        Returns
        -------
        list[dict[str, Any]]
            Task objects.
        """

        response = self._http_client.get(
            f"{self._config.graph_url}/me/todo/lists/{list_id}/tasks",
            headers=self._headers(include_content_type=False),
        )
        self._raise_for_status(response)
        return list(response.json().get("value", []))

    def create_task(
        self,
        list_id: str,
        title: str,
        body: str = "",
        due_datetime: str | None = None,
    ) -> dict[str, Any]:
        """Create a task in a To Do list.

        Parameters
        ----------
        list_id
            To Do list ID.
        title
            Task title.
        body
            Optional note body.
        due_datetime
            Optional ISO datetime.

        Returns
        -------
        dict[str, Any]
            Created task response.
        """

        task_data: dict[str, Any] = {"title": title}
        if body:
            task_data["body"] = {"content": body, "contentType": "text"}
        if due_datetime:
            task_data["dueDateTime"] = {
                "dateTime": due_datetime,
                "timeZone": self._config.default_timezone,
            }
        response = self._http_client.post(
            f"{self._config.graph_url}/me/todo/lists/{list_id}/tasks",
            headers=self._headers(),
            json=task_data,
        )
        self._raise_for_status(response)
        return dict(response.json())

    def complete_task(self, list_id: str, task_id: str) -> dict[str, Any]:
        """Mark a To Do task complete.

        Parameters
        ----------
        list_id
            To Do list ID.
        task_id
            Task ID.

        Returns
        -------
        dict[str, Any]
            Updated task response.
        """

        response = self._http_client.patch(
            f"{self._config.graph_url}/me/todo/lists/{list_id}/tasks/{task_id}",
            headers=self._headers(),
            json={"status": "completed"},
        )
        self._raise_for_status(response)
        return dict(response.json())

    def delete_task(self, list_id: str, task_id: str) -> None:
        """Delete a To Do task.

        Parameters
        ----------
        list_id
            To Do list ID.
        task_id
            Task ID.
        """

        response = self._http_client.delete(
            f"{self._config.graph_url}/me/todo/lists/{list_id}/tasks/{task_id}",
            headers=self._headers(include_content_type=False),
        )
        self._raise_for_status(response)


class OutlookCalendarClient(MicrosoftGraphClient):
    """Client for Outlook Calendar via Microsoft Graph."""

    def get_calendar_events(self) -> dict[str, Any]:
        """Read Outlook calendar events.

        Returns
        -------
        dict[str, Any]
            Microsoft Graph events response.
        """

        response = self._http_client.get(
            f"{self._config.graph_url}/me/events",
            headers={
                **self._headers(include_content_type=False),
                "Prefer": f'outlook.timezone="{self._config.default_timezone}"',
            },
        )
        self._raise_for_status(response)
        return dict(response.json())

    def create_appointment(
        self,
        subject: str,
        start_datetime: str,
        end_datetime: str,
        body: str = "",
    ) -> dict[str, Any]:
        """Create an Outlook calendar appointment.

        Parameters
        ----------
        subject
            Appointment subject.
        start_datetime
            Start ISO datetime.
        end_datetime
            End ISO datetime.
        body
            HTML body.

        Returns
        -------
        dict[str, Any]
            Created event response.
        """

        appointment_data = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body},
            "start": {
                "dateTime": start_datetime,
                "timeZone": self._config.default_timezone,
            },
            "end": {
                "dateTime": end_datetime,
                "timeZone": self._config.default_timezone,
            },
        }
        response = self._http_client.post(
            f"{self._config.graph_url}/me/events",
            headers=self._headers(),
            json=appointment_data,
        )
        self._raise_for_status(response)
        return dict(response.json())


class OutlookEmailClient(MicrosoftGraphClient):
    """Client for Outlook mail via Microsoft Graph."""

    def archive_email(self, message_id: str) -> None:
        """Move an email to the archive folder.

        Parameters
        ----------
        message_id
            Microsoft Graph message ID.
        """

        response = self._http_client.post(
            f"{self._config.graph_url}/me/messages/{message_id}/move",
            headers=self._headers(),
            json={"destinationId": "archive"},
        )
        self._raise_for_status(response)

    def flag_email(self, message_id: str, flagged: bool = True) -> None:
        """Set or clear an email flag.

        Parameters
        ----------
        message_id
            Microsoft Graph message ID.
        flagged
            Whether the email should be flagged.
        """

        response = self._http_client.patch(
            f"{self._config.graph_url}/me/messages/{message_id}",
            headers=self._headers(),
            json={"flag": {"flagStatus": "flagged" if flagged else "notFlagged"}},
        )
        self._raise_for_status(response)

    def mark_as_read(self, message_id: str, is_read: bool = True) -> None:
        """Set an email read state.

        Parameters
        ----------
        message_id
            Microsoft Graph message ID.
        is_read
            Desired read state.
        """

        response = self._http_client.patch(
            f"{self._config.graph_url}/me/messages/{message_id}",
            headers=self._headers(),
            json={"isRead": is_read},
        )
        self._raise_for_status(response)

    def delete_email(self, message_id: str) -> None:
        """Delete an email.

        Parameters
        ----------
        message_id
            Microsoft Graph message ID.
        """

        response = self._http_client.delete(
            f"{self._config.graph_url}/me/messages/{message_id}",
            headers=self._headers(include_content_type=False),
        )
        self._raise_for_status(response)

    def read_messages(
        self,
        folder: str = "Inbox",
        flagged: bool = False,
        unread: bool = False,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Read messages from a folder.

        Parameters
        ----------
        folder
            Mail folder name.
        flagged
            Whether to include flagged messages only.
        unread
            Whether to include unread messages only.
        limit
            Maximum number of messages.

        Returns
        -------
        list[dict[str, Any]]
            Message payloads.
        """

        filters = []
        if unread:
            filters.append("isRead eq false")
        if flagged:
            filters.append("flag/flagStatus eq 'flagged'")
        url = f"{self._config.graph_url}/me/mailFolders/{folder}/messages?$top={limit}"
        if filters:
            url += f"&$filter={' and '.join(filters)}"
        response = self._http_client.get(
            url,
            headers=self._headers(include_content_type=False),
        )
        self._raise_for_status(response)
        return list(response.json().get("value", []))

    def create_email_draft(
        self,
        subject: str,
        body: str,
        to_recipients: list[str],
        cc_recipients: list[str] | None = None,
        bcc_recipients: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create an Outlook email draft.

        Parameters
        ----------
        subject
            Draft subject.
        body
            HTML body.
        to_recipients
            Recipient email addresses.
        cc_recipients
            Optional CC addresses.
        bcc_recipients
            Optional BCC addresses.

        Returns
        -------
        dict[str, Any]
            Draft message response.
        """

        draft = self.__build_message(
            subject, body, to_recipients, cc_recipients, bcc_recipients
        )
        response = self._http_client.post(
            f"{self._config.graph_url}/me/messages",
            headers=self._headers(),
            json=draft,
        )
        self._raise_for_status(response)
        return dict(response.json())

    def send_email(
        self,
        subject: str,
        body: str,
        to_recipients: list[str],
        cc_recipients: list[str] | None = None,
        bcc_recipients: list[str] | None = None,
    ) -> None:
        """Send an Outlook email.

        Parameters
        ----------
        subject
            Email subject.
        body
            HTML body.
        to_recipients
            Recipient email addresses.
        cc_recipients
            Optional CC addresses.
        bcc_recipients
            Optional BCC addresses.
        """

        message = self.__build_message(
            subject, body, to_recipients, cc_recipients, bcc_recipients
        )
        response = self._http_client.post(
            f"{self._config.graph_url}/me/sendMail",
            headers=self._headers(),
            json={"message": message},
        )
        self._raise_for_status(response)

    def reply_to_email(
        self, message_id: str, body: str, reply_all: bool = False
    ) -> None:
        """Reply to an Outlook email.

        Parameters
        ----------
        message_id
            Microsoft Graph message ID.
        body
            Reply body.
        reply_all
            Whether to reply-all.
        """

        endpoint = "replyAll" if reply_all else "reply"
        response = self._http_client.post(
            f"{self._config.graph_url}/me/messages/{message_id}/{endpoint}",
            headers=self._headers(),
            json={"comment": body},
        )
        self._raise_for_status(response)

    def forward_email(
        self, message_id: str, to_recipients: list[str], comment: str = ""
    ) -> None:
        """Forward an Outlook email.

        Parameters
        ----------
        message_id
            Microsoft Graph message ID.
        to_recipients
            Recipient email addresses.
        comment
            Forward comment.
        """

        response = self._http_client.post(
            f"{self._config.graph_url}/me/messages/{message_id}/forward",
            headers=self._headers(),
            json={
                "comment": comment,
                "toRecipients": self.__recipient_payload(to_recipients),
            },
        )
        self._raise_for_status(response)

    def add_attachment_to_draft(
        self,
        draft_id: str,
        filename: str,
        content_bytes: bytes,
        mime_type: str = "application/octet-stream",
    ) -> None:
        """Attach a file to an Outlook draft.

        Parameters
        ----------
        draft_id
            Draft message ID.
        filename
            Attachment filename.
        content_bytes
            Attachment content.
        mime_type
            Attachment MIME type.
        """

        attachment = {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": filename,
            "contentType": mime_type,
            "contentBytes": base64.b64encode(content_bytes).decode("utf-8"),
        }
        response = self._http_client.post(
            f"{self._config.graph_url}/me/messages/{draft_id}/attachments",
            headers=self._headers(),
            json=attachment,
        )
        self._raise_for_status(response)

    def __build_message(
        self,
        subject: str,
        body: str,
        to_recipients: list[str],
        cc_recipients: list[str] | None,
        bcc_recipients: list[str] | None,
    ) -> dict[str, Any]:
        message = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body},
            "toRecipients": self.__recipient_payload(to_recipients),
        }
        if cc_recipients:
            message["ccRecipients"] = self.__recipient_payload(cc_recipients)
        if bcc_recipients:
            message["bccRecipients"] = self.__recipient_payload(bcc_recipients)
        return message

    def __recipient_payload(
        self, recipients: list[str]
    ) -> list[dict[str, dict[str, str]]]:
        return [{"emailAddress": {"address": recipient}} for recipient in recipients]
