import devOS.use_cases.manage_git_repo as manage_git_repo
import devOS.use_cases.code_gen.contracts.sync_contracts as sync_contracts
import os
import subprocess
from devOS.infrastructure import os_adapter
from devOS.infrastructure import scaffold_adapters
import pathlib
import dotenv
from devOS.use_cases import use_cases
import devOS.use_cases.config_project as config_project_module

# ======================= #
#                         #
#   CONSTRUCT USE CASES   #
#                         #
# ======================= #

# A fresh clone bootstraps by hand-writing only the devos_redis_*
# lines into .env, so the CLI reads them from there before reaching the store.
# The path is explicit because a bare load_dotenv() searches upwards from this
# module's own directory, which would find devOS's .env rather than the
# project's. Real environment variables still win, since load_dotenv does not
# override what is already set.
dotenv.load_dotenv(pathlib.Path(os.getcwd()) / ".env", interpolate=False)

console = os_adapter.OperatingSystemAdapter(os.getcwd())
config_project = config_project_module.ConfigProjectUseCase(
    pathlib.Path.cwd(), console, scaffold_adapters.GitProjectAdapter()
)
project_structure = config_project.execute()
git = manage_git_repo.ManageGitRepositoryUseCase(console)
contract_sync = sync_contracts.SyncContractsUseCase(project_structure=project_structure)
docstrings_formatter = use_cases.GenerateDocstringsUseCase(subprocess.run)
context_builder = use_cases.AggregateContextUseCase()


# ============================== #
#                                #
#   DEFINE USER INPUT MAPPER     #
#                                #
# ============================== #

mapper = {
    "commit": {"leaf node": git.add_commit_message},
    "release": {"leaf node": git.release_new_version},
    "version": {"leaf node": git.display_current_version},
    "build": {
        "context": {"leaf node": context_builder.execute},
    },
    "add": {
        "docs": {"leaf node": docstrings_formatter.execute},
    },
    "sync": {"leaf node": contract_sync.execute},
    "config": {"leaf node": config_project.set_update_existing_config().execute},
    "setup": {"leaf node": config_project.initial_setup},
}
