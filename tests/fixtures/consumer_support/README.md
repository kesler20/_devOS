# Independent consumer support fixture

This test-owned installation contains the canonical CRUD bundle, its SQL database
companion and the configuration bundle from automation_engine's wiki/Snippets/python. It is a complete
local import boundary for the selected SQL consumer tests. CI needs no adjacent
wiki checkout, credentials or private repository access.

The source files are wiki/Snippets/python/crud/use_cases.py and
wiki/Snippets/python/adapters_clients/database/sql_database_adapter.py in
C:/Users/Kesler/protocol/automation_engine. The installation follows the Snippets
SOP. The config directory supplies the existing offline credential contract checks.
Agents maintain this fixture deliberately when its consumer tests require
updated support. Recurring devOS generation does not install or rewrite it.
