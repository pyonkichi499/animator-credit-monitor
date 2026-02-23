import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage

import requests


def _decode_template_escapes(template: str) -> str:
    return (
        template.replace(r"\r\n", "\r\n")
        .replace(r"\n", "\n")
        .replace(r"\r", "\r")
        .replace(r"\t", "\t")
    )


def _render_template(template: str, title: str, message: str) -> str:
    try:
        return _decode_template_escapes(template).format(title=title, message=message)
    except KeyError as e:
        missing = e.args[0]
        raise ValueError(f"Unknown template variable: {missing}") from e


class Notifier(ABC):
    @abstractmethod
    def notify(self, title: str, message: str) -> None:
        ...


class ConsoleNotifier(Notifier):
    def notify(self, title: str, message: str) -> None:
        print(f"[{title}] {message}")


class MultiNotifier(Notifier):
    def __init__(self, notifiers: list[Notifier]) -> None:
        self._notifiers = notifiers

    def notify(self, title: str, message: str) -> None:
        for notifier in self._notifiers:
            notifier.notify(title, message)


class EmailNotifier(Notifier):
    def __init__(
        self,
        host: str,
        port: int,
        from_addr: str,
        to_addr: str,
        username: str = "",
        password: str = "",
        use_tls: bool = True,
        subject_template: str = "{title}",
        body_template: str = "{message}",
    ) -> None:
        self._host = host
        self._port = port
        self._from_addr = from_addr
        self._to_addr = to_addr
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._subject_template = subject_template
        self._body_template = body_template

    def notify(self, title: str, message: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = _render_template(self._subject_template, title, message)
        msg["From"] = self._from_addr
        msg["To"] = self._to_addr
        msg.set_content(_render_template(self._body_template, title, message))

        with smtplib.SMTP(self._host, self._port, timeout=30) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username and self._password:
                smtp.login(self._username, self._password)
            smtp.send_message(msg)


class LineNotifier(Notifier):
    def __init__(
        self,
        token: str,
        api_url: str = "https://notify-api.line.me/api/notify",
        message_template: str = "{title}\n{message}",
    ) -> None:
        self._token = token
        self._api_url = api_url
        self._message_template = message_template

    def notify(self, title: str, message: str) -> None:
        payload = {"message": _render_template(self._message_template, title, message)}
        headers = {"Authorization": f"Bearer {self._token}"}
        resp = requests.post(self._api_url, data=payload, headers=headers, timeout=30)
        resp.raise_for_status()
