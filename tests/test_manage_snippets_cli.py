from pathlib import Path

from devOS.use_cases.manage_snippets import ManageSnippetsUseCase


class DummyOSInterface:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute_command(self, command: str):
        self.last_command = command


def test_get_snippet_lists_folder_contents_when_source_is_directory(
    tmp_path, monkeypatch, capsys
):
    snippets_repository = tmp_path / "snippets"
    snippet_folder = snippets_repository / "python" / "utils"
    snippet_folder.mkdir(parents=True)
    (snippet_folder / "file_io.py").write_text("print('file io')", encoding="utf-8")
    (snippet_folder / "dynamic_array.py").write_text(
        "print('dynamic array')", encoding="utf-8"
    )
    monkeypatch.setattr(
        "devOS.use_cases.manage_snippets.use_cases.OSInterface", DummyOSInterface
    )

    snippet_manager = ManageSnippetsUseCase(str(snippets_repository))

    snippet_manager.get("from", "python,utils")

    captured = capsys.readouterr()

    assert str(snippet_folder) in captured.out
    assert "file_io.py" in captured.out
    assert "dynamic_array.py" in captured.out


def test_get_snippet_prints_file_contents_when_source_is_file(
    tmp_path, monkeypatch, capsys
):
    snippets_repository = tmp_path / "snippets"
    snippet_file = snippets_repository / "prompts" / "AGENTS.md"
    snippet_file.parent.mkdir(parents=True)
    snippet_file.write_text("# Agent instructions", encoding="utf-8")
    monkeypatch.setattr(
        "devOS.use_cases.manage_snippets.use_cases.OSInterface", DummyOSInterface
    )

    snippet_manager = ManageSnippetsUseCase(str(snippets_repository))

    snippet_manager.get("from", "prompts,AGENTS.md")

    captured = capsys.readouterr()

    assert captured.out == "# Agent instructions\n"


def test_get_snippet_copies_file_when_destination_is_provided(
    tmp_path, monkeypatch
):
    snippets_repository = tmp_path / "snippets"
    snippet_file = snippets_repository / "python" / "adapters.py"
    snippet_file.parent.mkdir(parents=True)
    snippet_file.write_text("adapter_content = True", encoding="utf-8")
    destination_file = tmp_path / "local" / "adapters.py"
    monkeypatch.setattr(
        "devOS.use_cases.manage_snippets.use_cases.OSInterface", DummyOSInterface
    )
    monkeypatch.chdir(tmp_path)

    snippet_manager = ManageSnippetsUseCase(str(snippets_repository))

    snippet_manager.get(
        "from",
        "python,adapters.py",
        "to",
        "local,adapters.py",
    )

    assert destination_file.read_text(encoding="utf-8") == "adapter_content = True"
