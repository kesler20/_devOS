"""Credential commands independent of project setup and Git initialization."""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import subprocess
import sys
import typing

import dotenv
import pyperclip

from devOS.domain import entities
import devOS.infrastructure.credential_vault as credential_vault
import devOS.use_cases.manage_credentials as manage_credentials


class CredentialParser(argparse.ArgumentParser):
    def error(self, message: str) -> typing.NoReturn:
        raise credential_vault.VaultError(
            "Invalid credential arguments. Use dev <command> --help."
        )


def get_project_name(root: pathlib.Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        return None
    name = result.stdout.strip().rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    credential_vault.validate_project(name)
    return name


def require_project(root: pathlib.Path) -> str:
    name = get_project_name(root)
    if name is None:
        raise credential_vault.VaultError(
            "Project scope requires a repository with an origin remote."
        )
    return name


def resolve_scope(
    document: dict[str, entities.JSONValue],
    key: str,
    root: pathlib.Path,
    project: bool,
    explicit_root: bool,
    setting: bool = False,
) -> str | None:
    credential_vault.validate_root_key(key)
    if project:
        return credential_vault.PROJECT_PREFIX + require_project(root)
    if explicit_root or setting:
        return None
    name = get_project_name(root)
    scope = credential_vault.PROJECT_PREFIX + name if name else None
    bundle = document.get(scope, {}) if scope else {}
    root_found = key in document
    project_found = isinstance(bundle, dict) and key in bundle
    if root_found and project_found:
        raise credential_vault.VaultError(
            "Key exists in root and project. Specify --root or --project."
        )
    return scope if project_found else None


def merge_bundle(
    existing: dict[str, entities.JSONValue],
    incoming: dict[str, entities.JSONValue],
    force: bool = False,
) -> dict[str, entities.JSONValue]:
    conflicts = sorted(
        key for key in incoming if key in existing and incoming[key] != existing[key]
    )
    if conflicts and not force:
        raise credential_vault.VaultError(
            "Conflicting credential keys: "
            + ", ".join(conflicts)
            + ". Use --force after choosing the source."
        )
    return {**existing, **incoming}


def execute(
    options: argparse.Namespace,
    vault: credential_vault.JSONCredentialVaultAdapter,
    root: pathlib.Path,
) -> None:
    document = vault.read()
    action = options.action
    if action == "config":
        print("Credential vault configured.")
        return
    if action == "list":
        print("Root")
        for key in sorted(document):
            if not key.startswith(credential_vault.PROJECT_PREFIX):
                print("  " + key)
        for scope in sorted(
            key for key in document if key.startswith(credential_vault.PROJECT_PREFIX)
        ):
            print("Project " + scope.removeprefix(credential_vault.PROJECT_PREFIX))
            for key in sorted(
                typing.cast(dict[str, entities.JSONValue], document[scope])
            ):
                print("  " + key)
        return
    if action in {"materialise", "import", "export"}:
        name = require_project(root)
        scope = credential_vault.PROJECT_PREFIX + name
        bundle = typing.cast(dict[str, entities.JSONValue], document.get(scope, {}))
        if action == "materialise":
            if scope not in document:
                raise credential_vault.VaultError(
                    "No credentials are assigned to this project."
                )
            manage_credentials.ManageCredentialsUseCase(
                vault, name, root
            ).get_credentials()
            return
        remote = credential_vault.get_remote_store(vault, options.store)
        key = "devos:projects:" + name
        names = [
            item.removeprefix(credential_vault.PROJECT_PREFIX)
            for item in document
            if item.startswith(credential_vault.PROJECT_PREFIX)
        ]
        if any(
            other != name
            and remote.get_storage_identity("devos:projects:" + other)
            == remote.get_storage_identity(key)
            for other in names
        ):
            raise credential_vault.VaultError(
                "Project names map to the same Prefect block."
            )
        stored = remote.get(key)
        if action == "import":
            if stored is None:
                raise credential_vault.VaultError(
                    "Remote project bundle does not exist."
                )
            incoming = entities.CredentialBundle.from_json_value(
                stored, "remote project"
            ).values()
            document[scope] = merge_bundle(bundle, incoming, options.force)
            vault.write(document)
            print(
                "Imported project credentials into the vault. Run dev materialise creds separately."
            )
        else:
            if scope not in document:
                raise credential_vault.VaultError(
                    "No credentials are assigned to this project."
                )
            if stored is not None and not options.force:
                raise credential_vault.VaultError(
                    "Remote bundle exists. Use --force to replace it."
                )
            if not remote.put(key, bundle) or remote.get(key) != bundle:
                raise credential_vault.VaultError("Remote export readback failed.")
            print("Project export verified.")
        return
    selected_scope = resolve_scope(
        document, options.key, root, options.project, options.root, action == "set"
    )
    bundle = (
        document
        if selected_scope is None
        else typing.cast(
            dict[str, entities.JSONValue], document.get(selected_scope, {})
        ).copy()
    )
    if action == "set":
        if options.key in bundle and not options.force:
            raise credential_vault.VaultError(
                "Credential already exists in this scope. Use --force to overwrite or --project to select project scope."
            )
        bundle[options.key] = options.value
    elif options.key not in bundle:
        raise credential_vault.VaultError(
            "Credential key is absent from the selected scope."
        )
    elif action == "get":
        value = bundle[options.key]
        pyperclip.copy(
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        )
        print("Credential copied to clipboard.")
        return
    elif action == "delete":
        del bundle[options.key]
    if selected_scope:
        document[selected_scope] = bundle
    vault.write(document)
    print("Credential vault updated.")


def handles(arguments: list[str]) -> bool:
    if not arguments:
        return False
    if arguments[0] == "delete":
        return True
    if arguments[0] in {"set", "get", "list", "materialise", "import", "export"}:
        return True
    return arguments[:2] == ["config", "creds"]


def main(
    arguments: list[str],
    vault: credential_vault.JSONCredentialVaultAdapter | None = None,
    root: pathlib.Path | None = None,
) -> int:
    parser = CredentialParser(
        prog="dev", description="Manage the local JSON credential vault."
    )
    commands = parser.add_subparsers(
        dest="action", required=True, parser_class=CredentialParser
    )
    for action in (
        "set",
        "get",
        "list",
        "delete",
        "materialise",
        "import",
        "export",
        "config",
    ):
        command = commands.add_parser(action)
        if action != "delete":
            command.add_argument("kind", choices=["creds"])
        if action in {"set", "get", "delete"}:
            command.add_argument("key")
            if action == "set":
                command.add_argument("value")
            scope = command.add_mutually_exclusive_group()
            scope.add_argument("--root", action="store_true")
            scope.add_argument("--project", action="store_true")
        if action in {"import", "export"}:
            command.add_argument("store")
        if action in {"set", "import", "export"}:
            command.add_argument("--force", action="store_true")
        command.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    try:
        options = parser.parse_args(arguments)
        logging.info("Starting credential operation %s", options.action)
        vault = vault or credential_vault.JSONCredentialVaultAdapter(
            credential_vault.get_configured_vault(interactive=sys.stdin.isatty())
        )
        execute(options, vault, root or pathlib.Path.cwd())
        logging.info("Completed credential operation %s", options.action)
        return 0
    except credential_vault.VaultError as error:
        logging.warning("Credential operation failed validation")
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        logging.warning("Credential operation failed")
        print(
            "Credential operation failed. Check vault permissions, configuration and remote availability.",
            file=sys.stderr,
        )
        return 1
