# Adapter and Client Snippets

Reusable adapter and client patterns extracted from `things_to_keep` and
`automation_engine`.

The snippets are intentionally dependency-injected. Production code can pass real
SDK clients, while tests use fakes and mocks without touching cloud services or
credential files.

## Contents

- `aws/clients.py` - AWS session wrapper for S3, DynamoDB, and generic resources.
- `aws/mqtt_client_adapter.py` - AWS IoT MQTT adapter.
- `aws/object_storage_adapter.py` - S3 object storage adapter.
- `database/sql_database_adapter.py` - SQLAlchemy CRUD adapter with session injection.
- `email/smtp_email_adapter.py` - plain SMTP and Gmail app-password SMTP email adapters.
- `google/clients.py` - Google OAuth service base, Gmail, Calendar, and Tasks clients.
- `google/email_adapter.py` - normalized Gmail email adapter.
- `microsoft/graph_clients.py` - Microsoft Graph base, To Do, Outlook Calendar, and Outlook Email clients.
- `microsoft/email_adapter.py` - normalized Outlook email adapter.
- `minio/object_storage_adapter.py` - MinIO object storage adapter.
- `mlflow/experiment_tracking_adapter.py` - MLflow experiment tracking adapter based on modelops `ExperimentTracking`.
- `mqtt/client_adapters.py` - shared MQTT adapter and Mosquitto/Paho adapter based on `wiz_iot_hub`.
- `oauth/server.py` - generic OAuth callback server factory plus one-shot local callback helper.
- `redis/key_value_adapters.py` - DynamoDB, Redis string, Redis hash, RedisTimeSeries, file key-value, file NoSQL, and JSON cache adapters.
- `rest/api_clients.py` - generic bearer-token REST client plus TickTick, Mendeley, and Monzo specializations.
- `storage/object_storage_adapters.py` - local filesystem object storage.
- `workflow/email_adapter.py` - Prefect email block adapter.
- `workflow/prefect_adapters.py` - Prefect workflow deployment, orchestration, and failure notification adapters.
- `tests/` - Offline tests for every snippet module.

## Source Lineage

- `C:\Users\Kesler\protocol\things_to_keep\aws_api`
- `C:\Users\Kesler\protocol\things_to_keep\google_api`
- `C:\Users\Kesler\protocol\things_to_keep\dsd_backend`
- `C:\Users\Kesler\protocol\things_to_keep\adapters.py`
- `C:\Users\Kesler\protocol\wiz_iot_hub\src\wiz_iot_hub\adapters.py`
- `C:\Users\Kesler\protocol\modelops\src\modelops\use_cases.py`
- `C:\Users\Kesler\protocol\modelops\src\modelops\domain.py`
- `C:\Users\Kesler\protocol\automation_engine\src\automation_engine\infrastructure\connectors`
- `C:\Users\Kesler\protocol\automation_engine\src\automation_engine\infrastructure\adapters.py`

## Usage

Copy a whole module or the full folder into a project, then replace the fake test
objects with real SDK clients at the boundary.

```bash
dev get snippet folder from python,adapters_clients to src,my_project,infrastructure
```
