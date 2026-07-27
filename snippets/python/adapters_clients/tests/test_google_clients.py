from adapters_clients.google.clients import (
    GmailClient,
    GoogleCalendarClient,
    GoogleClientConfig,
    GoogleOAuthServiceClient,
    GoogleTasksClient,
)


class Executable:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeMessages:
    def __init__(self) -> None:
        self.sent_body = None
        self.pages = [
            {"messages": [{"id": "1"}], "nextPageToken": "next"},
            {"messages": [{"id": "2"}]},
        ]
        self.deleted_body = None

    def send(self, userId, body):
        self.sent_body = body
        return Executable({"id": "sent"})

    def list(self, userId, q, pageToken=None):
        page = self.pages[0] if pageToken is None else self.pages[1]
        return Executable(page)

    def batchDelete(self, userId, body):
        self.deleted_body = body
        return Executable({"deleted": body["ids"]})


class FakeUsers:
    def __init__(self) -> None:
        self.messages_api = FakeMessages()

    def messages(self):
        return self.messages_api


class FakeEvents:
    def __init__(self) -> None:
        self.deleted_ids = []

    def insert(self, calendarId, body):
        return Executable({"calendarId": calendarId, **body})

    def list(self, calendarId, singleEvents, timeMin, timeMax):
        return Executable({"items": [{"id": "event-1"}]})

    def delete(self, calendarId, eventId):
        self.deleted_ids.append(eventId)
        return Executable({})


class FakeTaskLists:
    def list(self):
        return Executable({"items": [{"id": "tasks-1", "title": "Main"}]})


class FakeTasks:
    def __init__(self) -> None:
        self.inserted_body = None

    def insert(self, tasklist, body):
        self.inserted_body = body
        return Executable({"id": "task-2", **body})

    def list(self, tasklist):
        return Executable({"items": [{"id": "task-1", "title": "Buy milk"}]})

    def patch(self, tasklist, task, body):
        return Executable({"id": task, **body})


class FakeGoogleService:
    def __init__(self) -> None:
        self.users_api = FakeUsers()
        self.events_api = FakeEvents()
        self.tasklists_api = FakeTaskLists()
        self.tasks_api = FakeTasks()

    def users(self):
        return self.users_api

    def events(self):
        return self.events_api

    def tasklists(self):
        return self.tasklists_api

    def tasks(self):
        return self.tasks_api


def make_service_client(service):
    return GoogleOAuthServiceClient(
        GoogleClientConfig(
            api_name="gmail",
            api_version="v1",
            scopes=("scope",),
            client_secret_file="client.json",
            token_directory="tokens",
        ),
        service=service,
    )


def test_gmail_send_search_and_delete() -> None:
    service = FakeGoogleService()
    client = GmailClient(
        make_service_client(service), "sender@example.com", "to@example.com"
    )

    assert client.send_email("hello", "Subject") == {"id": "sent"}
    assert "raw" in service.users_api.messages_api.sent_body
    assert client.search_messages("from:someone") == [{"id": "1"}, {"id": "2"}]
    assert client.delete_messages("from:someone") == {"deleted": ["1", "2"]}


def test_calendar_client_add_list_and_delete() -> None:
    service = FakeGoogleService()
    client = GoogleCalendarClient(make_service_client(service))

    assert client.add_event({"summary": "Demo"}) == {
        "calendarId": "primary",
        "summary": "Demo",
    }
    assert client.list_events() == [{"id": "event-1"}]

    client.delete_events_by_ids(["event-1"])
    assert service.events_api.deleted_ids == ["event-1"]


def test_tasks_client_create_and_complete() -> None:
    service = FakeGoogleService()
    client = GoogleTasksClient(make_service_client(service))

    assert client.get_tasklist_id("Main") == "tasks-1"
    assert client.create_task("Buy milk", "Main")["title"] == "Buy milk"
    assert client.mark_task_as_complete("Buy milk", "Main") == {
        "id": "task-1",
        "status": "completed",
    }
