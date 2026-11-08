"""Run verified migration without modifying Redis."""
import argparse
import json
import dataclasses
from devOS.infrastructure import adapters
import pathlib
from devOS.infrastructure.credential_vault import JSONCredentialVaultAdapter, get_configured_vault, VaultError
from devOS.use_cases import migrate_credential_store

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol-root", required=True, type=pathlib.Path)
    parser.add_argument("--keep-local", nargs=2, action="append", default=[])
    options = parser.parse_args()
    choices = {}
    for project, key in options.keep_local:
        choices.setdefault(project, set()).add(key)
    projects = [p for p in options.protocol_root.iterdir() if p.is_dir() and (p / ".git").exists()]
    try:
        print(json.dumps(dataclasses.asdict(migrate_credential_store.MigrateCredentialStoreUseCase(JSONCredentialVaultAdapter(get_configured_vault()), adapters.build_redis_client, adapters.RedisNoSQLAdapter).execute(projects, choices))))
    except VaultError as error:
        parser.exit(1, str(error) + "\n")

if __name__ == "__main__":
    main()
