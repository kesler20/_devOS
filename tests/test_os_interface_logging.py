import sys

import devOS.use_cases.use_cases as use_cases


class FailingStdout:
    def __init__(self) -> None:
        self.encoding = "cp1252"
        self.writes: list[str] = []

    def write(self, text: str) -> int:
        if "🙀" in text or "😼" in text:
            raise UnicodeEncodeError("charmap", text, 0, 1, "character maps to <undefined>")
        self.writes.append(text)
        return len(text)

    def flush(self) -> None:
        return None


def test_log_message_replaces_unencodable_unicode(monkeypatch) -> None:
    fake_stdout = FailingStdout()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    interface = use_cases.OSInterface("C:/tmp")
    interface.log_message("Failed to fetch remote tags: 😱", error=True)

    combined_output = "".join(fake_stdout.writes)
    assert "Failed to fetch remote tags:" in combined_output
    assert "?" in combined_output
