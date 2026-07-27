from __future__ import annotations

from adapters_clients.microsoft.graph_clients import OutlookEmailClient


class OutlookEmailAdapter:
    """Normalized email adapter backed by Microsoft Graph Outlook mail.

    Parameters
    ----------
    outlook_client
        Outlook Graph client snippet.
    """

    def __init__(self, outlook_client: OutlookEmailClient) -> None:
        self.__outlook_client = outlook_client

    def send_email(
        self,
        subject: str,
        body: str,
        recipient: str | list[str],
        cc_recipients: list[str] | None = None,
        bcc_recipients: list[str] | None = None,
    ) -> bool:
        """Send an email through Outlook.

        Parameters
        ----------
        subject
            Email subject.
        body
            HTML body.
        recipient
            Recipient address or addresses.
        cc_recipients
            Optional CC addresses.
        bcc_recipients
            Optional BCC addresses.

        Returns
        -------
        bool
            True when the Graph request succeeds.
        """

        recipients = [recipient] if isinstance(recipient, str) else recipient
        self.__outlook_client.send_email(
            subject=subject,
            body=body,
            to_recipients=recipients,
            cc_recipients=cc_recipients,
            bcc_recipients=bcc_recipients,
        )
        return True
