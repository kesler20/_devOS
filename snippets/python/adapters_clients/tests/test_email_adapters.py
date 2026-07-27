from adapters_clients.email.smtp_email_adapter import (
    GmailAppPasswordSMTPEmailAdapter,
    SMTPEmailConfig,
    SimpleSMTPEmailAdapter,
)
from adapters_clients.google.email_adapter import GmailEmailAdapter
from adapters_clients.microsoft.email_adapter import OutlookEmailAdapter
from adapters_clients.workflow.email_adapter import PrefectEmailAdapter


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.login_call = None
        self.messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        self.login_call = (username, password)

    def send_message(self, message):
        self.messages.append(message)


def test_simple_smtp_email_adapter_sends_message() -> None:
    FakeSMTP.instances.clear()
    adapter = SimpleSMTPEmailAdapter(
        SMTPEmailConfig(username="sender@example.com", password="password"),
        smtp_factory=FakeSMTP,
    )

    assert (
        adapter.send_email(
            subject="Hello",
            body="Body",
            recipient=["a@example.com", "b@example.com"],
        )
        is True
    )
    smtp = FakeSMTP.instances[0]
    assert smtp.started_tls is True
    assert smtp.login_call == ("sender@example.com", "password")
    assert smtp.messages[0]["To"] == "a@example.com, b@example.com"


def test_gmail_app_password_adapter_uses_smtp_defaults() -> None:
    adapter = GmailAppPasswordSMTPEmailAdapter(
        SMTPEmailConfig(username="sender@gmail.com", password="app-password")
    )

    message = adapter.build_message(
        subject="Hello",
        body="Body",
        recipient="owner@example.com",
    )

    assert message["From"] == "sender@gmail.com"
    assert message["To"] == "owner@example.com"


class FakeGmailClient:
    def __init__(self):
        self.calls = []

    def send_email(self, body, subject, recipient, attachments=None):
        self.calls.append((body, subject, recipient, attachments))
        return {"id": "gmail-message"}


def test_gmail_email_adapter_normalizes_send_call() -> None:
    client = FakeGmailClient()
    adapter = GmailEmailAdapter(client)

    assert adapter.send_email("Subject", "Body", "to@example.com") == {
        "id": "gmail-message"
    }
    assert client.calls == [("Body", "Subject", "to@example.com", None)]


class FakeOutlookClient:
    def __init__(self):
        self.calls = []

    def send_email(
        self,
        subject,
        body,
        to_recipients,
        cc_recipients=None,
        bcc_recipients=None,
    ):
        self.calls.append((subject, body, to_recipients, cc_recipients, bcc_recipients))


def test_outlook_email_adapter_normalizes_recipient() -> None:
    client = FakeOutlookClient()
    adapter = OutlookEmailAdapter(client)

    assert adapter.send_email("Subject", "<p>Body</p>", "to@example.com") is True
    assert client.calls == [("Subject", "<p>Body</p>", ["to@example.com"], None, None)]


class FakePrefectEmailSender:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return "sent"


def test_prefect_email_adapter_calls_prefect_email_task() -> None:
    sender = FakePrefectEmailSender()
    adapter = PrefectEmailAdapter(credentials="creds", send_message=sender)

    assert adapter.send_email("Subject", "Body", "to@example.com") == "sent"
    assert sender.calls == [
        {
            "email_server_credentials": "creds",
            "subject": "Subject",
            "msg": "Body",
            "email_to": ["to@example.com"],
            "html": False,
        }
    ]
