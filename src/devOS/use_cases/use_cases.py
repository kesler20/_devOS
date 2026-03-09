from __future__ import annotations
from pathlib import Path
import json
import re
import subprocess
import os
import time
import colorama  # type: ignore


class OSInterface:
    """Provide scoped OS operations with logging.

    Attributes
    ----------
    directory : str
        Target directory to execute commands in.
    previous_directory : str
        Working directory before entering the context manager.
    """

    def __init__(self, directory: str):
        """Initialize the interface with a target directory.

        Parameters
        ----------
        directory : str
            Directory to switch into when used as a context manager.
        """
        self.directory = directory
        self.previous_directory = os.getcwd()

    def __enter__(self) -> OSInterface:
        self.previous_directory = os.getcwd()
        self.log_message(f"changing directory to {self.directory}")
        os.chdir(self.directory)
        return self

    def __exit__(self, *args) -> None:
        self.log_message(f"changing directory to {self.previous_directory}")
        os.chdir(self.previous_directory)

    def log_message(
        self, message: str, error: bool = False, is_command: bool = False
    ) -> None:
        """Print a formatted message to the console.

        Parameters
        ----------
        message : str
            the message to print
        error : bool, optional
            whether the message is an error message, by default False
        is_command : bool, optional
            whether the message is a command, by default False

        Notes
        -----
        If the message is empty i.e. `log_message("")`,
        the method will print a new line and wait for 1 second.
        """
        if message == "":
            time.sleep(1)
            print("\n")
        emoji = "🙀" if error else "😼"
        if is_command is False:
            msg = f"{emoji} ------------- {message}"
        else:
            msg = f"\n{emoji} | {self.directory} - {message} \n"

        if error:
            print(f"{colorama.Fore.RED}{msg}{colorama.Style.RESET_ALL}")
        else:
            print(msg)

    def execute_command(self, command: str, error: bool = False) -> None:
        """Execute a command using `os.system`.

        Parameters
        ----------
        command : str
            The command to execute.
        error : bool, optional
            Whether to log the command as an error, by default False.

        Notes
        -----
        For echo commands, pass arguments directly to the shell to avoid
        quoting pitfalls.

        Examples
        --------
        >>> execute_command("python --version")
        """

        if error:
            self.log_message(command, error=True, is_command=True)

        self.log_message(command, error=error, is_command=True)
        os.system(command)

    @staticmethod
    def get_home_path() -> str:
        """Return the user home directory path.

        Returns
        -------
        str
            Home directory path.
        """
        return os.path.expanduser("~")

    @staticmethod
    def join(*paths: str) -> str:
        """Join multiple path components into a single path.

        Parameters
        ----------
        *paths : str
            Path components to join.

        Returns
        -------
        str
            Joined path.
        """
        if len(paths) == 0:
            raise ValueError("At least one path component must be provided.")
        elif len(paths) == 1:
            return paths[0]
        else:
            return os.path.join(*paths)


class GenerateDocstringsUseCase:

    def _find_repo_root(self, start: Path | None = None) -> Path:
        p = (start or Path.cwd()).resolve()
        for candidate in [p, *p.parents]:
            if (candidate / ".git").exists():
                return candidate
        return p  # best-effort fallback

    def run_codex_format_numpy_docstrings(self, title: str, prompt_body: str) -> int:
        repo_root = self._find_repo_root()
        full_prompt = f"{title}\n\n{prompt_body}\n"

        # Local Codex: use stdin (`-`) to avoid Windows command-length + quoting problems.
        # Send UTF-8 bytes explicitly to avoid codepage/UTF-8 mismatch.
        result = subprocess.run(
            ["codex.cmd", "--full-auto", "exec", "-"],
            cwd=repo_root,
            input=full_prompt.encode("utf-8", errors="replace"),
            check=False,
        )
        return result.returncode

    def execute(self):
        TITLE = "[codex] WI-01 Format docstrings under src/** (NumPy style)"
        PROMPT = """Context:
- Follow AGENTS.md for project-specific conventions (tests, style, architecture).
- Goal: reformat/add docstrings using the NumPy docstring standard.

Scope:
- Only modify files under: src/**
- Do not touch tests/, docs/, configs, or tooling.

Process (do this in order):
1) Planning pass:
   - Enumerate all Python modules under src/**.
   - Identify all classes and their methods (and module-level functions) that are missing docstrings or not in NumPy format.
   - Print a concise checklist of targets (file → symbols) before editing anything.

2) Editing pass:
   - For each target symbol, add/reformat docstrings to NumPy style:
     - Use sections only when relevant: Parameters, Returns, Raises, Yields, Attributes, See Also, Notes, Examples.
     - Keep it minimal: do not rewrite code, do not rename symbols, do not refactor.
     - If a method/function has no type hints:
       - Use parameter names from the signature; add types only if obvious.
       - Infer return type from the implementation where reasonable; otherwise omit “Returns” and provide only a short description.
     - Include an “Examples” section only when it is small and clear; prefer 1–3 lines.

3) Quality:
   - Preserve behavior exactly (docstrings only).
   - Keep diffs minimal and localized.
   - Run the project’s standard test command from AGENTS.md; if none is specified, run pytest.
   - If any test fails, fix only what is necessary.

Output:
- Summarize: files changed, tests run, and any edge cases where return types could not be inferred.
"""
        raise SystemExit(self.run_codex_format_numpy_docstrings(TITLE, PROMPT))


class AggregateContextUseCase:
    def execute(self, input_extensions: str, directory: str | Path) -> Path:
        """
        Walk `directory` recursively, collect contents of files matching `extensions`,
        and write a single concatenated context file to the directory root as `context.txt`.

        Each file is separated by a header:

        ===========================================
                                  PATH/TO/FILENAME
        ===========================================

        Parameters
        ----------
        input_extensions
            Comma separated file extensions to include, e.g. .ts,.tsx, .py Case-insensitive.
        directory
            Root directory to walk.

        Returns
        -------
        Path
            Path to the written context file (`<directory>/context.txt`).
        """
        extensions = input_extensions.split(",")
        root = Path(directory).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"directory must be an existing folder: {root}")

        exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
        out_path = root / "context.txt"

        # Collect files deterministically
        files: list[Path] = []
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in exts:
                # Avoid including the output file if extensions include ".txt"
                if p.resolve() != out_path.resolve():
                    files.append(p)

        files.sort(key=lambda x: str(x.relative_to(root)).lower())

        header_width = 43  # matches your example length
        line = "=" * header_width

        def format_header(rel_path: str) -> str:
            # Center the path in a fixed-width line (truncate from the left if too long)
            if len(rel_path) > header_width:
                rel_path = rel_path[-header_width:]
            return rel_path.center(header_width)

        with out_path.open("w", encoding="utf-8", newline="\n") as out:
            for i, f in enumerate(files):
                rel = f.relative_to(root).as_posix()
                out.write(f"{line}\n{format_header(rel)}\n{line}\n")
                try:
                    out.write(f.read_text(encoding="utf-8"))
                except UnicodeDecodeError:
                    # Fall back to a permissive read if some file isn't valid UTF-8
                    out.write(f.read_text(encoding="utf-8", errors="replace"))
                out.write("\n\n")

        return out_path

def main() -> int:
    GenerateDocstringsUseCase().execute()
    return 0


if __name__ == "__main__":
    main()
