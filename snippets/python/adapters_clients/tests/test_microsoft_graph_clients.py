from adapters_clients.microsoft.graph_clients import (
    MicrosoftGraphConfig,
    MicrosoftToDoClient,
    OutlookCalendarClient,
    OutlookEmailClient,
)


class FakeResponse:
    def __init__(self, payload=None) -> None:
        self.payload = payload or {}

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class FakeHTTPClient:
    def __init__(self) -> None:
        self.calls = []

    def get(self, url, headers=None):
        self.calls.append(("GET", url, headers, None))
        if url.endswith("/me/todo/lists"):
            return FakeResponse({"value": [{"id": "list-1", "displayName": "Agenda"}]})
        if "/tasks" in url:
            return FakeResponse({"value": [{"id": "task-1", "title": "Demo"}]})
        if url.endswith("/me/events"):
            return FakeResponse({"value": [{"id": "event-1"}]})
        return FakeResponse({"value": [{"id": "message-1"}]})

    def post(self, url, headers=None, json=None):
        self.calls.append(("POST", url, headers, json))
        return FakeResponse({"id": "created", **(json or {})})

    def patch(self, url, headers=None, json=None):
        self.calls.append(("PATCH", url, headers, json))
        return FakeResponse({"id": "updated", **(json or {})})

    def delete(self, url, headers=None):
        self.calls.append(("DELETE", url, headers, None))
        return FakeResponse({})


def test_microsoft_todo_client() -> None:
    http_client = FakeHTTPClient()
    client = MicrosoftToDoClient(http_client, lambda: "token")

    assert client.get_list_id_by_name("Agenda") == "list-1"
    assert client.create_task_list("Agenda")["displayName"] == "Agenda"
    assert client.get_tasks("list-1") == [{"id": "task-1", "title": "Demo"}]
    assert (
        client.create_task("list-1", "Demo", due_datetime="2026-07-24T09:00:00")[
            "title"
        ]
        == "Demo"
    )
    assert client.complete_task("list-1", "task-1")["status"] == "completed"
    client.delete_task("list-1", "task-1")

    assert any(call[0] == "DELETE" for call in http_client.calls)


def test_outlook_calendar_client() -> None:
    http_client = FakeHTTPClient()
    client = OutlookCalendarClient(
        http_client,
        lambda: "token",
        MicrosoftGraphConfig(default_timezone="Europe/London"),
    )

    assert client.get_calendar_events() == {"value": [{"id": "event-1"}]}
    created = client.create_appointment(
        "Meeting",
        "2026-07-24T09:00:00",
        "2026-07-24T10:00:00",
    )

    assert created["subject"] == "Meeting"


def test_outlook_email_client() -> None:
    http_client = FakeHTTPClient()
    client = OutlookEmailClient(http_client, lambda: "token")

    client.archive_email("message-1")
    client.flag_email("message-1")
    client.mark_as_read("message-1")
    client.delete_email("message-1")
    assert client.read_messages(unread=True) == [{"id": "message-1"}]
    assert (
        client.create_email_draft("Subject", "Body", ["a@example.com"])["subject"]
        == "Subject"
    )
    client.send_email("Subject", "Body", ["a@example.com"])
    client.reply_to_email("message-1", "Reply")
    client.forward_email("message-1", ["b@example.com"])
    client.add_attachment_to_draft("draft-1", "file.txt", b"hello", "text/plain")

    assert any("/attachments" in call[1] for call in http_client.calls)
