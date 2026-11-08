# Remote credential loading

These examples are independent of automation_engine. Copy this complete package into a Python project and add its selected requirements file. Add application fields to the typed settings class.

Local projects normally use materialized `.env` files. Install this example only for explicit remote loading. Set `devos_project_name` to the exported project name. For Redis set `devos_store=redis` and either `devos_redis_url` or the separate host, port, username, password, db and ssl fields. For Prefect set `devos_store=prefect`, `PREFECT_API_URL` and, when required, `PREFECT_API_KEY`.

The Prefect Secret block holds the JSON project bundle. A project named sample maps to `devos-projects-sample`. Publish it with `dev export creds STORENAME` before running. The loader only reads. The optional adapter ensure method creates a missing block only when explicitly called with a seed payload.

`LoadingCredsUseCase.from_environment().execute()` loads the project bundle before settings construction. Root credentials are never inherited. Null values and reserved devos_ settings leave the existing environment untouched. The local `.env` and shell remain the fallback for unavailable Redis.

Run the offline tests with `python -m pytest examples/credentials/tests`.
