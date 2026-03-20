
class GmailNotificationAdapter:
    """Simple SMTP email adapter for Gmail app-password authentication."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        smtp_server: str | None = None,
        smtp_port: int | None = None,
        use_tls: bool | None = None,
        timeout_seconds: int = 20,
    ) -> None:
        self.username = username or configs.EmailConfigsCreds.EMAIL_HOST_USER.value
        self.password = password or configs.EmailConfigsCreds.EMAIL_HOST_PASSWORD.value
        self.smtp_server = smtp_server or configs.EmailConfigsCreds.SMTP_SERVER.value
        self.smtp_port = int(
            smtp_port
            if smtp_port is not None
            else configs.EmailConfigsCreds.SMTP_PORT.value
        )
        self.use_tls = (
            bool(use_tls)
            if use_tls is not None
            else bool(configs.EmailConfigsCreds.SMTP_USE_TLS.value)
        )
        self.timeout_seconds = timeout_seconds

    def _validate_credentials(self) -> None:
        if not self.username:
            raise ValueError("EMAIL_HOST_USER is required to send email.")
        if not self.password:
            raise ValueError("EMAIL_HOST_PASSWORD is required to send email.")

    def send_email(
        self,
        subject: str,
        body: str,
        to: str | list[str] | None = None,
        html: bool = True,
        from_email: str | None = None,
    ) -> bool:
        if to is None:
            to = [self.username]  # type: ignore
            
        self._validate_credentials()

        recipients = [to] if isinstance(to, str) else to
        if len(recipients) == 0:
            raise ValueError("At least one recipient is required.")

        sender = from_email or str(self.username)
        message = EmailMessage()
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject

        if html:
            message.set_content("This is an HTML email. Use an HTML-capable client.")
            message.add_alternative(body, subtype="html")
        else:
            message.set_content(body)

        try:
            with smtplib.SMTP(
                host=self.smtp_server,
                port=self.smtp_port,
                timeout=self.timeout_seconds,
            ) as smtp:
                if self.use_tls:
                    smtp.starttls()
                smtp.login(str(self.username), str(self.password))
                smtp.send_message(message)

            return True
        except Exception as error:
            print(f"Error sending email: {error}")
            return False