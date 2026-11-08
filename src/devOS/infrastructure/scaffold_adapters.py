"""Project files, Git index operations, and devOS bootstrap retrieval."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import subprocess
import tempfile
import typing

import dotenv

import devOS.domain.scaffold as scaffold
from devOS.use_cases import credential_ports

BOOTSTRAP_NAMES = tuple(
    f"devos_redis_{key}"
    for key in ("url", "host", "port", "username", "password", "db", "ssl")
)


class DevOSSecretAdapter:
    """Read explicitly assigned root credentials from the local vault."""

    def __init__(self, vault: credential_ports.CredentialStorePort) -> None:
        self.__vault = vault

    def get(self, key: str) -> str:
        """Retrieve one value without printing it or returning it in a result model."""
        logging.info("Reading assigned root credential")
        values = self.__vault.get("devos:general")
        if not isinstance(values, dict) or key not in values:
            logging.warning("Assigned root credential is absent")
            raise scaffold.ScaffoldError(
                "credentials", "Referenced root credential key is absent"
            )
        value = values[key]
        logging.info("Read assigned root credential")
        return value if isinstance(value, str) else json.dumps(value)


def read_bootstrap_file(path: pathlib.Path) -> dict[str, str]:
    """Read only canonical bootstrap assignments, preserving literal values."""
    if not path.is_file():
        raise scaffold.ScaffoldError(
            "bootstrap", "Selected bootstrap file does not exist"
        )
    values = dotenv.dotenv_values(path, interpolate=False)
    return {
        key.lower(): value
        for key, value in values.items()
        if key.lower() in BOOTSTRAP_NAMES and value is not None
    }


class BootstrapSourceAdapter:
    """Resolve each explicitly selected store without modifying os.environ."""

    def __init__(self, secrets: DevOSSecretAdapter):
        self.__secrets = secrets

    def resolve(self, source: scaffold.BootstrapSource) -> dict[str, str]:
        values = (
            read_bootstrap_file(source.env_file.expanduser().resolve())
            if source.env_file
            else {}
        )
        for target, secret_key in source.secret_keys.items():
            values[target] = self.__secrets.get(secret_key)
        if not values.get("devos_redis_url") and not values.get("devos_redis_host"):
            raise scaffold.ScaffoldError(
                "bootstrap", "Select a Redis URL or host source"
            )
        return values


class GitProjectAdapter:
    """Operate on explicit paths without invoking commit or push helpers."""

    def __init__(self) -> None:
        pass

    def get_repository_name(self, root: pathlib.Path) -> str:
        result = self.run(root, ["remote", "get-url", "origin"], allow_failure=True)
        if result.returncode:
            return root.name
        name = result.stdout.strip().rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        return name or root.name

    def run(
        self, root: pathlib.Path, arguments: list[str], allow_failure: bool = False
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        if result.returncode and not allow_failure:
            raise scaffold.ScaffoldError(
                "git", "Git command failed. Inspect repository state before retrying"
            )
        return result

    def is_repository(self, root: pathlib.Path) -> bool:
        if not root.is_dir():
            return False
        result = self.run(root, ["rev-parse", "--show-toplevel"], allow_failure=True)
        return (
            result.returncode == 0
            and pathlib.Path(result.stdout.strip()).resolve() == root.resolve()
        )

    def staged(self, root: pathlib.Path) -> list[str]:
        return [
            name
            for name in self.run(
                root, ["diff", "--cached", "--name-only", "-z"]
            ).stdout.split("\0")
            if name
        ]

    def validate_target(
        self, root: pathlib.Path, name: str, desired: str, expected_hash: str | None
    ) -> None:
        """Refuse to stage unrelated edits in a file the scaffold also changes."""
        if not self.is_repository(root):
            return
        indexed = self.run(root, ["show", f":{name}"], allow_failure=True)
        if indexed.returncode:
            return
        worktree = (
            (root / name).read_text(encoding="utf-8") if (root / name).exists() else ""
        )
        if name in self.staged(root) and (
            indexed.stdout != desired.replace("\r\n", "\n")
            or indexed.stdout != worktree
        ):
            raise scaffold.ScaffoldError(
                "preflight",
                f"Preserve existing staged changes in {name} before scaffolding",
                "conflict",
            )
        if indexed.stdout == worktree:
            return
        # A retry can stage an already-rendered approved file when its index still
        # matches the inspected original. Other overlapping user edits need review.
        digest = hashlib.sha256(indexed.stdout.encode()).hexdigest()
        if worktree == desired and expected_hash == digest:
            return
        raise scaffold.ScaffoldError(
            "preflight",
            f"Review overlapping working or staged edits in {name}",
            "conflict",
        )

    def initialise(self, root: pathlib.Path) -> None:
        if not self.is_repository(root):
            parent = self.run(
                root, ["rev-parse", "--show-toplevel"], allow_failure=True
            )
            if parent.returncode == 0:
                raise scaffold.ScaffoldError(
                    "git", "Project is nested inside another Git repository"
                )
            self.run(root, ["init", "-b", "main"])

    def configure_origin(self, root: pathlib.Path, repository: str) -> None:
        """Set a missing origin and reject a mismatched existing one."""
        result = self.run(root, ["remote", "get-url", "origin"], allow_failure=True)
        if result.returncode == 0:
            current = result.stdout.strip().rstrip("/").removesuffix(".git")
            allowed = {
                f"https://github.com/{repository}",
                f"git@github.com:{repository}",
            }
            if current not in allowed:
                raise scaffold.ScaffoldError(
                    "git",
                    "Existing origin differs from the selected GitHub repository",
                    "conflict",
                )
        else:
            self.run(
                root,
                ["remote", "add", "origin", f"https://github.com/{repository}.git"],
            )

    def stage(self, root: pathlib.Path, files: list[str]) -> list[str]:
        if files:
            self.run(root, ["add", "--", *sorted(set(files))])
        return sorted(set(files))


class ProjectFilesAdapter:
    """Read and write only approved, contained project paths."""

    def __init__(self) -> None:
        pass

    def path(self, root: pathlib.Path, relative: str) -> pathlib.Path:
        if "\\" in relative or ":" in relative:
            raise scaffold.ScaffoldError(
                "preflight", "Use relative project paths with forward slashes"
            )
        name = pathlib.Path(relative)
        if (
            name.is_absolute()
            or ".." in name.parts
            or any(part.lower() == ".git" for part in name.parts)
            or not name.parts
        ):
            raise scaffold.ScaffoldError(
                "preflight", "File paths must be relative project paths outside .git"
            )
        target = root.joinpath(name)
        if not target.resolve().is_relative_to(root.resolve()):
            raise scaffold.ScaffoldError(
                "preflight", "File path escapes the project through a symlink"
            )
        if any(
            part.is_symlink()
            for part in [target, *target.parents]
            if part.is_relative_to(root)
        ):
            raise scaffold.ScaffoldError(
                "preflight", "Scaffold targets cannot be symlinks"
            )
        return target

    def read(self, path: pathlib.Path) -> str:
        return path.read_bytes().decode("utf-8") if path.is_file() else ""

    def inventory(self, root: pathlib.Path) -> dict[str, str]:
        """Return file fingerprints without disclosing environment contents."""
        result: dict[str, str] = {}
        if not root.is_dir():
            return result
        excluded = {
            ".git",
            ".venv",
            "node_modules",
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
            "htmlcov",
            "dist",
            "build",
            ".devos_backup",
        }
        for folder, directories, names in os.walk(root, followlinks=False):
            directories[:] = [
                name
                for name in directories
                if name not in excluded and not pathlib.Path(folder, name).is_symlink()
            ]
            for name in names:
                path = pathlib.Path(folder, name)
                if path.is_symlink() or (
                    name.startswith(".env") and name not in {".env", ".env.example"}
                ):
                    continue
                if path.suffix in {
                    ".py",
                    ".md",
                    ".json",
                    ".toml",
                    ".yaml",
                    ".yml",
                    ".tsx",
                    ".ts",
                    ".txt",
                } or name in {
                    ".gitignore",
                    "Dockerfile",
                    "AGENTS.md",
                    ".env",
                    ".env.example",
                    "uv.lock",
                }:
                    result[path.relative_to(root).as_posix()] = hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
        return dict(sorted(result.items()))

    def preflight(
        self,
        root: pathlib.Path,
        rendered: dict[str, str],
        expected: dict[str, str],
        git: GitProjectAdapter,
    ) -> None:
        for name, content in rendered.items():
            target = self.path(root, name)
            if target.exists() and not target.is_file():
                raise scaffold.ScaffoldError(
                    "preflight", f"File target is a directory at {name}"
                )
            if target.is_file() and self.read(target) != content:
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                if expected.get(name) != digest:
                    raise scaffold.ScaffoldError(
                        "preflight",
                        f"Reinspect and approve the current file at {name}",
                        "conflict",
                    )
            git.validate_target(root, name, content, expected.get(name))

    def write(self, root: pathlib.Path, rendered: dict[str, str]) -> list[str]:
        for name, content in rendered.items():
            target = self.path(root, name)
            if self.read(target) == content and target.is_file():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.encode("utf-8"))
        return sorted(rendered)

    def write_environment(
        self, root: pathlib.Path, values: dict[str, str], project_name: str
    ) -> list[str]:
        """Atomically replace .env only after the caller verifies every store."""
        environment = self.path(root, ".env")
        lines = [
            f"{key}={json.dumps(value, ensure_ascii=False)}"
            for key, value in sorted(values.items())
        ]
        lines.append(f"devos_project_name={json.dumps(project_name)}")
        with tempfile.NamedTemporaryFile(
            dir=root, prefix=".env.scaffold.", delete=False
        ) as stream:
            temporary = pathlib.Path(stream.name)
            stream.write(("\n".join(lines) + "\n").encode())
        try:
            temporary.replace(environment)
        finally:
            temporary.unlink(missing_ok=True)
        example = "".join(
            f"{key}=\n" for key in sorted([*values, "devos_project_name"])
        )
        self.path(root, ".env.example").write_bytes(example.encode())
        return [".env.example"]
