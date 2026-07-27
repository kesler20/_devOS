from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters_clients.google.clients import GmailClient


class GmailEmailAdapter:
    """Normalized email adapter backed by Gmail API.

    Parameters
    ----------
    gmail_client
        Gmail API client snippet.
    """

    def __init__(self, gmail_client: GmailClient) -> None:
        self.__gmail_client = gmail_client

    def send_email(
        self,
        subject: str,
        body: str,
        recipient: str,
        attachments: list[str | Path] | None = None,
    ) -> dict[str, Any]:
        """Send an email through Gmail API.

        Parameters
        ----------
        subject
            Email subject.
        body
            Plain text body.
        recipient
            Recipient address.
        attachments
            Optional attachment paths.

        Returns
        -------
        dict[str, Any]
            Gmail API send response.
        """

        return self.__gmail_client.send_email(
            body=body,
            subject=subject,
            recipient=recipient,
            attachments=attachments,
        )
