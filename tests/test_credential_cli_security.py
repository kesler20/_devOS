import sys

import devOS


def test_debug_output_redacts_positional_credential_value(
    monkeypatch, capsys
) -> None:
    received: list[tuple[str, str]] = []

    def set_credential(key: str, value: str) -> None:
        received.append((key, value))

    monkeypatch.setattr(sys, "argv", ["dev", "--debug"])

    devOS.execute_function(set_credential, "TOKEN", "secret-value")

    captured = capsys.readouterr()
    assert received == [("TOKEN", "secret-value")]
    assert "secret-value" not in captured.out
    assert "[redacted]" in captured.out
