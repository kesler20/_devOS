from devOS import run_server
from devOS.use_cases.manage_credentials import ManageCredentialsUseCase
from devOS.use_cases.manage_git_repo import ManageGitRepositoryUseCase
from devOS.use_cases.generate_code import GenerateCodeUseCase
import os
import pathlib
import dotenv
import devOS.infrastructure.adapters as adapters
from devOS.use_cases import use_cases
from devOS.use_cases.config_project import ConfigProjectUseCase

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
dotenv.load_dotenv(pathlib.Path(os.getcwd()) / ".env")

config_project = ConfigProjectUseCase()
project_structure = config_project.execute()
git = ManageGitRepositoryUseCase()
code_generator = GenerateCodeUseCase(project_structure=project_structure)
credentials_manager = ManageCredentialsUseCase(
    database=adapters.RedisNoSQLAdapter.from_environment(),
    project_name=project_structure.project_name,
    project_root=pathlib.Path(os.getcwd()),
)
docstrings_formatter = use_cases.GenerateDocstringsUseCase()
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
        "leaf node": code_generator.execute,
        "dao": {"leaf node": code_generator.generate_dao},
        "dto": {"leaf node": code_generator.generate_dto},
        "api": {"leaf node": code_generator.generate_endpoints},
        "tests": {
            "api": {"leaf node": code_generator.generate_tests_for_endpoints},
            "services": {"leaf node": code_generator.generate_tests_for_services},
        },
        "context": {"leaf node": context_builder.execute},
    },
    "set": {
        "credential": {"leaf node": credentials_manager.set_credential},
        "credentials": {"leaf node": credentials_manager.set_credentials},
        "secrets": {"leaf node": credentials_manager.set_global_secret},
    },
    "get": {
        "credentials": {"leaf node": credentials_manager.get_credentials},
        "secrets": {"leaf node": credentials_manager.get_global_secret},
    },
    "list": {
        "credentials": {"leaf node": credentials_manager.list_credentials},
    },
    "delete": {
        "credential": {"leaf node": credentials_manager.delete_credential},
        "secrets": {"leaf node": credentials_manager.delete_global_secret},
    },
    "export": {
        "credentials": {"leaf node": credentials_manager.export_credentials},
        "store": {"leaf node": credentials_manager.export_store},
    },
    "import": {
        "store": {"leaf node": credentials_manager.import_store},
    },
    "ui": {
        "leaf node": run_server.main,
    },
    "add": {
        "docs": {"leaf node": docstrings_formatter.execute},
    },
    "sync": {"leaf node": code_generator.sync_contracts},
    "config": {"leaf node": config_project.set_update_existing_config().execute},
    "setup": {
        "leaf node": config_project.initial_setup,
        "credentials": {
            "leaf node": lambda: credentials_manager.setup_credentials(
                snippets_root=pathlib.Path(
                    os.path.join(
                        os.path.expanduser("~"), *project_structure.home_root.snippets
                    )
                ),
                project_config=project_structure,
            )
        },
    },
}
