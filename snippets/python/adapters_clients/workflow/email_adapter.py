from __future__ import annotations

from typing import Any


class PrefectEmailAdapter:
    """Send email through Prefect email blocks.

    Parameters
    ----------
    credentials
        Prefect email credentials block or compatible object.
    send_message
        Function compatible with ``prefect_email.email_send_message``.
    """

    def __init__(self, credentials: Any, send_message: Any | None = None) -> None:
        self.__credentials = credentials
        self.__send_message = send_message

    def send_email(
        self,
        subject: str,
        body: str,
        recipient: str | list[str],
        html: bool = False,
    ) -> Any:
        """Send an email through Prefect.

        Parameters
        ----------
        subject
            Email subject.
        body
            Email body.
        recipient
            Recipient address or addresses.
        html
            Whether the body is HTML.

        Returns
        -------
        Any
            Prefect email task result.
        """

        if self.__send_message is None:
            from prefect_email import email_send_message

            self.__send_message = email_send_message
        recipients = [recipient] if isinstance(recipient, str) else recipient
        return self.__send_message(
            email_server_credentials=self.__credentials,
            subject=subject,
            msg=body,
            email_to=recipients,
            html=html,
        )
