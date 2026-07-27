from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage


@dataclass(frozen=True)
class SMTPEmailConfig:
    """SMTP email configuration.

    Parameters
    ----------
    username
        SMTP username, usually the sender email address.
    password
        SMTP password or provider app password.
    host
        SMTP host.
    port
        SMTP port.
    use_tls
        Whether to start TLS before login.
    timeout_seconds
        SMTP connection timeout.
    """

    username: str
    password: str
    host: str = "smtp.gmail.com"
    port: int = 587
    use_tls: bool = True
    timeout_seconds: int = 20


class SimpleSMTPEmailAdapter:
    """Send email through a plain SMTP server.

    Parameters
    ----------
    config
        SMTP connection configuration.
    smtp_factory
        Optional SMTP factory. Tests should inject this.
    """

    def __init__(
        self, config: SMTPEmailConfig, smtp_factory: type | None = None
    ) -> None:
        self.__config = config
        self.__smtp_factory = smtp_factory or smtplib.SMTP

    def build_message(
        self,
        subject: str,
        body: str,
        recipient: str | list[str],
        html: bool = False,
        sender: str | None = None,
    ) -> EmailMessage:
        """Build an SMTP email message.

        Parameters
        ----------
        subject
            Email subject.
        body
            Email body.
        recipient
            Recipient address or addresses.
        html
            Whether ``body`` is HTML.
        sender
            Optional sender address.

        Returns
        -------
        EmailMessage
            Ready-to-send email message.
        """

        recipients = [recipient] if isinstance(recipient, str) else recipient
        if not recipients:
            raise ValueError("At least one recipient is required.")

        message = EmailMessage()
        message["From"] = sender or self.__config.username
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        if html:
            message.set_content("This message requires an HTML-capable email client.")
            message.add_alternative(body, subtype="html")
        else:
            message.set_content(body)
        return message

    def send_email(
        self,
        subject: str,
        body: str,
        recipient: str | list[str],
        html: bool = False,
        sender: str | None = None,
    ) -> bool:
        """Send an SMTP email.

        Parameters
        ----------
        subject
            Email subject.
        body
            Email body.
        recipient
            Recipient address or addresses.
        html
            Whether ``body`` is HTML.
        sender
            Optional sender address.

        Returns
        -------
        bool
            True when the message is sent.
        """

        message = self.build_message(subject, body, recipient, html, sender)
        with self.__smtp_factory(
            host=self.__config.host,
            port=self.__config.port,
            timeout=self.__config.timeout_seconds,
        ) as smtp:
            if self.__config.use_tls:
                smtp.starttls()
            smtp.login(self.__config.username, self.__config.password)
            smtp.send_message(message)
        return True


class GmailAppPasswordSMTPEmailAdapter(SimpleSMTPEmailAdapter):
    """SMTP adapter configured for Gmail app-password authentication."""
