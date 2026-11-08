# Configuration bundle

Local projects load dotenv with interpolate=False before typed settings. Use dev set creds KEY VALUE --project to assign values and dev materialise creds separately inside the repository. Root values require explicit assignment and are never inherited. Get root values through dev get creds KEY --root.

The default settings example is configs.py. Redis and Prefect credential loaders are optional remote patterns, independent working copies with LoadingCredsUseCase live in devOS/examples/credentials. This bundle also includes read-only provider adapters and offline tests for explicitly selected remote use.

Install complete support under the Snippets SOP. Run python -m pytest wiki/Snippets/python/config/tests with its parent python folder on PYTHONPATH. Never commit local credential values.

## Prefect vault store

The loader reads from whichever store `devos_store` names: `redis` (default) or
`prefect`. `prefect_vault_adapter.py` implements the Prefect store with the same
`get(key)` contract. Each key maps to a Prefect `Secret` block holding the JSON bundle,
named with lowercase letters, digits and dashes (`devos:projects:sample` becomes
`devos-projects-sample`). `ensure(key, environment_payload)` loads the block when it
exists and otherwise creates it from the environment values that are set (secret
wrappers unwrapped), failing when there is nothing to seed it with, so a first run
creates the block and later runs only read it. It handles Prefect calls that are sync
or async.
Copy the adapter beside `credentials.py` and add `prefect` to
the target's dependencies only when this store is selected. Offline tests use a fake
block class and need no Prefect server.

