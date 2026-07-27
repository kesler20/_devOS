from __future__ import annotations

import base64
import pickle
from dataclasses import dataclass
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from mimetypes import guess_type
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GoogleClientConfig:
    """Configuration for a Google API client.

    Parameters
    ----------
    api_name
        Google API name, for example ``"gmail"``.
    api_version
        Google API version, for example ``"v1"``.
    scopes
        OAuth scopes requested by the client.
    client_secret_file
        Path to the Google OAuth client secret file.
    token_directory
        Directory where API-specific token pickle files are stored.
    """

    api_name: str
    api_version: str
    scopes: tuple[str, ...]
    client_secret_file: str | Path
    token_directory: str | Path


class GoogleOAuthServiceClient:
    """Create Google API service objects with cached OAuth credentials.

    Parameters
    ----------
    config
        Google API configuration.
    service
        Optional prebuilt Google service. Tests should inject this.
    flow_factory
        Optional factory compatible with
        ``InstalledAppFlow.from_client_secrets_file``.
    request_factory
        Optional request object factory used when refreshing credentials.
    build_service
        Optional function compatible with ``googleapiclient.discovery.build``.
    """

    def __init__(
        self,
        config: GoogleClientConfig,
        service: Any | None = None,
        flow_factory: Any | None = None,
        request_factory: Any | None = None,
        build_service: Any | None = None,
    ) -> None:
        self.__config = config
        self.__service = service
        self.__flow_factory = flow_factory
        self.__request_factory = request_factory
        self.__build_service = build_service

    def __token_path(self) -> Path:
        token_directory = Path(self.__config.token_directory)
        token_directory.mkdir(parents=True, exist_ok=True)
        return token_directory / (
            f"token_{self.__config.api_name}_{self.__config.api_version}.pickle"
        )

    def __load_credentials(self) -> Any | None:
        token_path = self.__token_path()
        if not token_path.exists():
            return None
        with token_path.open("rb") as token_file:
            return pickle.load(token_file)

    def __save_credentials(self, credentials: Any) -> None:
        with self.__token_path().open("wb") as token_file:
            pickle.dump(credentials, token_file)

    def get_service(self) -> Any:
        """Return a Google service object.

        Returns
        -------
        Any
            Google service object.
        """

        if self.__service is not None:
            return self.__service

        if self.__build_service is None:
            from googleapiclient.discovery import build

            self.__build_service = build
        if self.__flow_factory is None:
            from google_auth_oauthlib.flow import InstalledAppFlow

            self.__flow_factory = InstalledAppFlow.from_client_secrets_file
        if self.__request_factory is None:
            from google.auth.transport.requests import Request

            self.__request_factory = Request

        credentials = self.__load_credentials()
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(self.__request_factory())
            else:
                flow = self.__flow_factory(
                    str(self.__config.client_secret_file),
                    list(self.__config.scopes),
                )
                credentials = flow.run_local_server()
            self.__save_credentials(credentials)

        self.__service = self.__build_service(
            self.__config.api_name,
            self.__config.api_version,
            credentials=credentials,
        )
        return self.__service


class GmailClient:
    """Send, search, read, and delete Gmail messages through a Google service.

    Parameters
    ----------
    google_service_client
        Service client configured for Gmail.
    default_sender
        Sender address used when building messages.
    default_recipient
        Recipient used when no explicit recipient is passed.
    """

    def __init__(
        self,
        google_service_client: GoogleOAuthServiceClient,
        default_sender: str,
        default_recipient: str,
    ) -> None:
        self.__google_service_client = google_service_client
        self.__default_sender = default_sender
        self.__default_recipient = default_recipient

    def __get_service(self) -> Any:
        return self.__google_service_client.get_service()

    def add_attachment(self, message: MIMEMultipart, filename: str | Path) -> None:
        """Attach a file to a MIME message.

        Parameters
        ----------
        message
            Multipart message to mutate.
        filename
            File path to attach.

        Side Effects
        ------------
        Adds a MIME attachment to ``message``.
        """

        file_path = Path(filename)
        content_type, encoding = guess_type(str(file_path))
        if content_type is None or encoding is not None:
            content_type = "application/octet-stream"
        main_type, sub_type = content_type.split("/", 1)
        payload = file_path.read_bytes()

        if main_type == "text":
            attachment: MIMEText | MIMEImage | MIMEAudio | MIMEBase = MIMEText(
                payload.decode("utf-8"),
                _subtype=sub_type,
            )
        elif main_type == "image":
            attachment = MIMEImage(payload, _subtype=sub_type)
        elif main_type == "audio":
            attachment = MIMEAudio(payload, _subtype=sub_type)
        else:
            attachment = MIMEBase(main_type, sub_type)
            attachment.set_payload(payload)

        attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=file_path.name,
        )
        message.attach(attachment)

    def build_message(
        self,
        body: str,
        subject: str,
        recipient: str | None = None,
        attachments: list[str | Path] | None = None,
    ) -> dict[str, str]:
        """Build a Gmail raw message body.

        Parameters
        ----------
        body
            Plain-text email body.
        subject
            Email subject.
        recipient
            Recipient address. Defaults to ``default_recipient``.
        attachments
            Optional attachment paths.

        Returns
        -------
        dict[str, str]
            Gmail API body containing a base64url ``raw`` payload.
        """

        selected_recipient = recipient or self.__default_recipient
        selected_attachments = attachments or []
        if selected_attachments:
            message: MIMEMultipart | MIMEText = MIMEMultipart()
            message.attach(MIMEText(body, "plain"))
            for filename in selected_attachments:
                self.add_attachment(message, filename)
        else:
            message = MIMEText(body, "plain")

        message["to"] = selected_recipient
        message["from"] = self.__default_sender
        message["subject"] = subject
        return {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")}

    def send_email(
        self,
        body: str,
        subject: str,
        recipient: str | None = None,
        attachments: list[str | Path] | None = None,
    ) -> dict[str, Any]:
        """Send an email.

        Parameters
        ----------
        body
            Plain-text email body.
        subject
            Email subject.
        recipient
            Recipient address.
        attachments
            Optional attachment paths.

        Returns
        -------
        dict[str, Any]
            Gmail API response.
        """

        message = self.build_message(body, subject, recipient, attachments)
        return (
            self.__get_service()
            .users()
            .messages()
            .send(userId="me", body=message)
            .execute()
        )

    def search_messages(self, query: str) -> list[dict[str, Any]]:
        """Search Gmail messages with pagination.

        Parameters
        ----------
        query
            Gmail search query.

        Returns
        -------
        list[dict[str, Any]]
            Message metadata dictionaries.
        """

        messages_api = self.__get_service().users().messages()
        response = messages_api.list(userId="me", q=query).execute()
        messages = list(response.get("messages", []))
        while "nextPageToken" in response:
            response = messages_api.list(
                userId="me",
                q=query,
                pageToken=response["nextPageToken"],
            ).execute()
            messages.extend(response.get("messages", []))
        return messages

    def delete_messages(self, query: str) -> dict[str, Any]:
        """Delete all messages matching a Gmail query.

        Parameters
        ----------
        query
            Gmail search query.

        Returns
        -------
        dict[str, Any]
            Gmail batch delete response.
        """

        messages = self.search_messages(query)
        message_ids = [message["id"] for message in messages]
        if not message_ids:
            return {}
        return (
            self.__get_service()
            .users()
            .messages()
            .batchDelete(userId="me", body={"ids": message_ids})
            .execute()
        )


class GoogleCalendarClient:
    """Create, list, and delete Google Calendar events.

    Parameters
    ----------
    google_service_client
        Service client configured for Google Calendar.
    calendar_id
        Calendar ID used by default.
    """

    def __init__(
        self,
        google_service_client: GoogleOAuthServiceClient,
        calendar_id: str = "primary",
    ) -> None:
        self.__google_service_client = google_service_client
        self.__calendar_id = calendar_id

    def __events(self) -> Any:
        return self.__google_service_client.get_service().events()

    def add_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Create a calendar event.

        Parameters
        ----------
        event
            Google Calendar event body.

        Returns
        -------
        dict[str, Any]
            Created event response.
        """

        return (
            self.__events().insert(calendarId=self.__calendar_id, body=event).execute()
        )

    def list_events(
        self, time_min: str | None = None, time_max: str | None = None
    ) -> list[dict[str, Any]]:
        """List calendar events.

        Parameters
        ----------
        time_min
            Inclusive lower ISO datetime bound.
        time_max
            Exclusive upper ISO datetime bound.

        Returns
        -------
        list[dict[str, Any]]
            Calendar event bodies.
        """

        response = (
            self.__events()
            .list(
                calendarId=self.__calendar_id,
                singleEvents=True,
                timeMin=time_min,
                timeMax=time_max,
            )
            .execute()
        )
        return list(response.get("items", []))

    def delete_events_by_ids(self, event_ids: list[str]) -> None:
        """Delete calendar events by ID.

        Parameters
        ----------
        event_ids
            Event IDs to delete.

        Side Effects
        ------------
        Sends one delete request for each event ID.
        """

        for event_id in event_ids:
            self.__events().delete(
                calendarId=self.__calendar_id, eventId=event_id
            ).execute()


class GoogleTasksClient:
    """Create, list, update, and delete Google Tasks resources.

    Parameters
    ----------
    google_service_client
        Service client configured for Google Tasks.
    """

    def __init__(self, google_service_client: GoogleOAuthServiceClient) -> None:
        self.__google_service_client = google_service_client

    def __service(self) -> Any:
        return self.__google_service_client.get_service()

    def list_tasklists(self) -> list[dict[str, Any]]:
        """List Google task lists.

        Returns
        -------
        list[dict[str, Any]]
            Task list objects.
        """

        return list(self.__service().tasklists().list().execute().get("items", []))

    def get_tasklist_id(self, task_list_title: str) -> str | None:
        """Find a task list ID by title.

        Parameters
        ----------
        task_list_title
            Human-readable task list title.

        Returns
        -------
        str | None
            Task list ID, or ``None``.
        """

        for task_list in self.list_tasklists():
            if task_list.get("title") == task_list_title:
                return task_list.get("id")
        return None

    def create_task(
        self,
        title: str,
        task_list_title: str,
        notes: str | None = None,
        due: str | None = None,
    ) -> dict[str, Any] | None:
        """Create a task in a task list.

        Parameters
        ----------
        title
            Task title.
        task_list_title
            Task list title.
        notes
            Optional task notes.
        due
            Optional RFC3339 due datetime.

        Returns
        -------
        dict[str, Any] | None
            Created task response, or ``None`` if the task list is missing.
        """

        task_list_id = self.get_tasklist_id(task_list_title)
        if task_list_id is None:
            return None
        body = {"title": title, "notes": notes, "due": due, "status": "needsAction"}
        return (
            self.__service().tasks().insert(tasklist=task_list_id, body=body).execute()
        )

    def mark_task_as_complete(
        self, task_title: str, task_list_title: str
    ) -> dict[str, Any] | None:
        """Mark the first matching task complete.

        Parameters
        ----------
        task_title
            Task title.
        task_list_title
            Task list title.

        Returns
        -------
        dict[str, Any] | None
            Patched task response, or ``None`` when missing.
        """

        task_list_id = self.get_tasklist_id(task_list_title)
        if task_list_id is None:
            return None
        tasks_api = self.__service().tasks()
        tasks = tasks_api.list(tasklist=task_list_id).execute().get("items", [])
        selected_task = next(
            (task for task in tasks if task.get("title") == task_title),
            None,
        )
        if selected_task is None:
            return None
        return tasks_api.patch(
            tasklist=task_list_id,
            task=selected_task["id"],
            body={"status": "completed"},
        ).execute()
