from devOS import run_server
from devOS.use_cases.manage_git_repo import ManageGitRepositoryUseCase
from devOS.use_cases.manage_snippets import ManageSnippetsUseCase
from devOS.use_cases.generate_code import GenerateCodeUseCase
from devOS.use_cases.manage_credentials import ManageCredentialsUseCase
import os
from devOS.use_cases import use_cases
from devOS.use_cases.config_project import ConfigProjectUseCase

# ======================= #
#                         #
#   CONSTRUCT USE CASES   #
#                         #
# ======================= #

config_project = ConfigProjectUseCase()
project_structure = config_project.execute()
git = ManageGitRepositoryUseCase()
code_generator = GenerateCodeUseCase(project_structure=project_structure)
snippet_manager = ManageSnippetsUseCase(*project_structure.home_root.snippets)
credentials_manager = ManageCredentialsUseCase(
    project_structure.home_root.vault, os.getcwd().split(os.sep)
)
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
        "snippet": {
            "leaf node": snippet_manager.set,
            "folder": {"leaf node": snippet_manager.set_folder},
        },
        "credentials": {"leaf node": credentials_manager.set_credentials},
        "secrets": {"leaf node": credentials_manager.set_global_secret},
    },
    "get": {
        "snippets": {"leaf node": snippet_manager.show_snippets},
        "snippet": {
            "leaf node": snippet_manager.get,
            "folder": {"leaf node": snippet_manager.get_folder},
        },
        "credentials": {"leaf node": credentials_manager.get_credentials},
        "secrets": {"leaf node": credentials_manager.get_global_secret},
    },
    "delete": {
        "snippet": {"leaf node": snippet_manager.delete},
    },
    "ui": {
        "leaf node": run_server.main,
    },
    "sync": {"leaf node": code_generator.sync_contracts},
    "config": {"leaf node": config_project.set_update_existing_config().execute},
    "setup": {"leaf node": config_project.initial_setup},
}
