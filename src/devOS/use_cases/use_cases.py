from __future__ import annotations
import pathlib as pathlib
import json
import re
import subprocess
import os
import logging
import typing
import sys
import time
import colorama


class AggregateContextUseCase:
    def __init__(self) -> None:
        pass

    def execute(
        self, input_extensions: str, directory: str | pathlib.Path
    ) -> pathlib.Path:
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
        logging.info("Aggregating source context")
        extensions = input_extensions.split(",")
        root = pathlib.Path(directory).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"directory must be an existing folder: {root}")

        exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
        out_path = root / "context.txt"

        # Collect files deterministically
        files: list[pathlib.Path] = []
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in exts:
                # Avoid including the output file if extensions include ".txt"
                if p.resolve() != out_path.resolve():
                    files.append(p)

        files.sort(key=lambda x: str(x.relative_to(root)).lower())

        header_width = 43
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

        logging.info("Aggregated source context")
        return out_path


class GenerateDocstringsUseCase:
    def __init__(
        self, process_runner: typing.Callable[..., subprocess.CompletedProcess[bytes]]
    ) -> None:
        self.__process_runner = process_runner

    def execute(self) -> typing.NoReturn:
        logging.info("Formatting source docstrings")
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
       - Infer return type from the implementation where reasonable; otherwise omit "Returns" and provide only a short description.
     - Include an "Examples" section only when it is small and clear; prefer 1–3 lines.

3) Quality:
   - Preserve behavior exactly (docstrings only).
   - Keep diffs minimal and localized.
   - Run the project's standard test command from AGENTS.md; if none is specified, run pytest.
   - If any test fails, fix only what is necessary.

Output:
- Summarize: files changed, tests run, and any edge cases where return types could not be inferred.
"""
        root = pathlib.Path.cwd().resolve()
        repository_root = next(
            (
                candidate
                for candidate in [root, *root.parents]
                if (candidate / ".git").exists()
            ),
            root,
        )
        full_prompt = f"{TITLE}\n\n{PROMPT}\n"
        result = self.__process_runner(
            ["codex.cmd", "--full-auto", "exec", "-"],
            cwd=repository_root,
            input=full_prompt.encode("utf-8", errors="replace"),
            check=False,
        )
        logging.info("Docstring formatting completed with status %s", result.returncode)
        raise SystemExit(result.returncode)
