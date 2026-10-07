"""CLI dispatch that does not initialise the legacy project wizard or Git helpers."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import pydantic
import redis.exceptions

from devOS.domain.scaffold import ScaffoldError, ScaffoldSpec
from devOS.infrastructure.github_repository_client import GitHubRepositoryClient
from devOS.infrastructure.scaffold_adapters import BootstrapSourceAdapter, DevOSSecretClient, GitProjectAdapter, ProjectFilesAdapter
from devOS.use_cases.scaffold_project import (
    ConfigureGitHubSecretsUseCase, ConfigureProjectCredentialsUseCase,
    InspectProjectScaffoldUseCase, ScaffoldProjectUseCase,
)


def main(arguments: list[str] | None = None) -> int:
    """Read specs by path, emit value-free results, and return reliable failure codes."""
    parser = argparse.ArgumentParser(prog="dev scaffold")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("project_path", type=pathlib.Path)
    apply = commands.add_parser("apply")
    apply.add_argument("spec_path", type=pathlib.Path)
    commands.add_parser("schema")
    for command in ("credentials", "secrets"):
        operation = commands.add_parser(command).add_subparsers(dest="operation", required=True)
        operation.add_parser("apply").add_argument("spec_path", type=pathlib.Path)
    options = parser.parse_args(arguments)
    files, git = ProjectFilesAdapter(), GitProjectAdapter()
    result: pydantic.BaseModel
    try:
        if options.command == "schema":
            print(json.dumps(ScaffoldSpec.model_json_schema(), indent=2))
            return 0
        if options.command == "inspect":
            result = InspectProjectScaffoldUseCase(files, git).execute(options.project_path)
        else:
            spec = ScaffoldSpec.model_validate_json(options.spec_path.read_text(encoding="utf-8"))
            source = spec.secret_source_env_file or pathlib.Path(__file__).resolve().parents[2] / ".env"
            secret_client = DevOSSecretClient(source)
            bootstrap = BootstrapSourceAdapter(secret_client)
            credentials = ConfigureProjectCredentialsUseCase(bootstrap, files, git)
            if options.command == "credentials":
                result = credentials.execute(spec)
            else:
                if spec.github is None:
                    raise ScaffoldError("preflight", "Select GitHub repository and token key")
                github = GitHubRepositoryClient(pydantic.SecretStr(secret_client.get(spec.github.token_secret_key)))
                secrets = ConfigureGitHubSecretsUseCase(bootstrap, github)
                result = secrets.execute(spec) if options.command == "secrets" else ScaffoldProjectUseCase(credentials, secrets, bootstrap, github, files, git).execute(spec)
        print(result.model_dump_json(indent=2))
        return 0
    except ScaffoldError as error:
        print(json.dumps({"operation": error.operation, "reason": error.reason,
                          "category": error.category, "completed": error.completed}), file=sys.stderr)
        return 1
    except pydantic.ValidationError as error:
        # Pydantic's ordinary error string includes input values, which specs must
        # never echo even when a malformed file accidentally contains a secret.
        fields = [".".join(map(str, item["loc"])) for item in error.errors(include_input=False, include_context=False, include_url=False)]
        print(json.dumps({"operation": "spec", "category": "configuration", "invalid_fields": fields}), file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError, redis.exceptions.RedisError, KeyError):
        print(json.dumps({"operation": options.command, "category": "dependency",
                          "reason": "Dependency or input read failed. Inspect state before retrying"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
