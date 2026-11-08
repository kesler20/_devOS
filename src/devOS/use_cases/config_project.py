from __future__ import annotations

import logging
import pathlib
import typing
import colorama
import pydantic

from devOS.domain import entities
from devOS.infrastructure import os_adapter
from devOS.infrastructure import scaffold_adapters
from devOS.use_cases.utils import file_io


class ConfigProjectUseCase:
    def __init__(
        self,
        root: pathlib.Path,
        console: os_adapter.OperatingSystemAdapter,
        git: scaffold_adapters.GitProjectAdapter,
    ) -> None:
        self.__root = root
        self.__console = console
        self.__git = git
        self.update_existing_config = False

    def set_update_existing_config(self) -> ConfigProjectUseCase:
        self.update_existing_config = True
        return self

    def initial_setup(self) -> None:
        logging.info("Starting initial_setup")
        self.__console.execute_command("cd frontend && npm install")
        self.__console.execute_command("npm install -g @openai/codex")
        logging.info("Completed initial_setup")

    def execute(self, project_name: str | None = None) -> entities.ProjectConfigSchema:
        logging.info("Configuring project")
        project_name = project_name or self.__git.get_repository_name(self.__root)
        path = self.__root / "specs/project_config.json"
        if not self.update_existing_config:
            if not path.is_file():
                result = entities.ProjectConfigSchema.create_default(project_name)
                logging.info("Created default project configuration")
                return result
            try:
                result = entities.ProjectConfigSchema.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                logging.info("Loaded project configuration")
                return result
            except pydantic.ValidationError:
                logging.warning("Stored project configuration requires authoring")
                self.update_existing_config = True

        banner = "▣  devOS CONFIG WIZARD  ▣"
        print(
            colorama.Fore.GREEN
            + colorama.Style.BRIGHT
            + banner
            + colorama.Style.RESET_ALL
        )

        self.__console.log_message(
            "Let's set up your project configuration step by step.\n"
        )
        self.__console.log_message(
            "You can press Enter to accept the default value shown in [brackets].\n"
        )

        def get_default(path, fallback=""):
            """Helper to get a nested value from existing_config or fallback."""
            val = None
            if (
                self.update_existing_config
                and file_io.File("specs", "project_config.json").exists()
            ):
                val = file_io.File("specs", "project_config.json").get_json()
                try:
                    for key in path:
                        if isinstance(key, int):
                            val = val[key]
                        else:
                            val = val.get(key) if isinstance(val, dict) else val[key]
                        if val is None:
                            return fallback
                    if isinstance(val, list):
                        return ",".join(str(v) for v in val)
                    return str(val) if val is not None else fallback
                except (KeyError, IndexError, TypeError):
                    return fallback
            if val is None:
                return fallback
            return str(val)

        # Prompt for home_root directories
        self.__console.log_message(
            "The following information locates reusable snippets\n"
        )
        snippets = self.__console.prompt(
            "Enter the snippets directory (relative to home, comma-separated)",
            default=get_default(
                ["home_root", "snippets"], "protocol,automation_engine,wiki,Snippets"
            ),
        ).split(",")

        # Prompt for project_root directories
        self.__console.log_message(
            "The following information is used to configure code generation outputs\n"
        )
        dao_dir = self.__console.prompt_optional(
            "Enter the Data Access Object (DAO) output directory (relative to project root)",
            default=get_default(
                ["project_root", "dao_output_config", 0, "directory"],
                f"src,{project_name},domain,dao.py",
            ),
        )
        dto_dir = self.__console.prompt_optional(
            "Enter the Data Transfer Object (DTO) output directory (relative to project root)",
            default=get_default(
                ["project_root", "dto_output_config", 0, "directory"],
                f"src,{project_name},use_cases,dto.py",
            ),
        )
        api_dir = self.__console.prompt_optional(
            "Enter the API endpoints output directory (relative to project root)",
            default=get_default(
                ["project_root", "api_output_config", 0, "directory"],
                f"src,{project_name},infrastructure,routes.py",
            ),
        )
        test_services_dir = self.__console.prompt_optional(
            "Enter the test services output directory (relative to project root)",
            default=get_default(
                ["project_root", "test_services_output_directory", 0, "directory"],
                "tests",
            ),
        )
        test_routes_dir = self.__console.prompt_optional(
            "Enter the test routes output directory (relative to project root) ensure the index matches the api output directory!",
            default=get_default(
                ["project_root", "test_api_output_config", 0, "directory"],
                "tests,test_crud_routes.py",
            ),
        )

        adapter_dir = self.__console.prompt_optional(
            "Enter the adapters output directory (relative to project root)",
            default=get_default(
                ["project_root", "adapter_output_directory", 0, "directory"],
                f"src,{project_name},infrastructure,sqlalchemy_db_adapter.py",
            ),
        )

        use_cases_dir = self.__console.prompt_optional(
            "Enter the use cases output directory (relative to project root)",
            default=get_default(
                ["project_root", "use_cases_output_directory", 0, "directory"],
                f"src,{project_name},use_cases,crud_use_cases.py",
            ),
        )
        app_definition_dir = self.__console.prompt_optional(
            "Enter the app definition directory (relative to project root)",
            default=get_default(
                ["project_root", "app_definition_directory", 0, "directory"],
                f"src,{project_name},infrastructure,app.py",
            ),
        )

        dao_prog_lang = self.__console.prompt_optional(
            "Enter the programming language for DAO generation",
            default=get_default(
                ["project_root", "dao_output_config", 0, "language"], "python"
            ),
        )
        dto_prog_lang = self.__console.prompt_optional(
            "Enter the programming language for DTO generation",
            default=get_default(
                ["project_root", "dto_output_config", 0, "language"], "python"
            ),
        )
        api_prog_lang = self.__console.prompt_optional(
            "Enter the programming language for API endpoints generation ensure the index matches the api output directory!",
            default=get_default(
                ["project_root", "api_output_config", 0, "language"], "python"
            ),
        )
        test_api_prog_lang = self.__console.prompt_optional(
            "Enter the programming language for test routes generation",
            default=get_default(
                ["project_root", "test_api_output_config", 0, "language"], "python"
            ),
        )

        contract_sync_python_output_dir = self.__console.prompt_optional(
            "Enter the contract sync output directory for Python source files (writes TypeScript)",
            default=get_default(
                [
                    "project_root",
                    "contract_sync_output_config",
                    0,
                    "output_directory",
                ],
                f"src,{project_name},schema,typescript",
            ),
        )
        contract_sync_typescript_output_dir = self.__console.prompt_optional(
            "Enter the contract sync output directory for TypeScript source files (writes Python)",
            default=get_default(
                [
                    "project_root",
                    "contract_sync_output_config",
                    1,
                    "output_directory",
                ],
                f"src,{project_name},schema,python",
            ),
        )

        # Build the project configuration
        project_config = entities.ProjectConfigSchema(
            project_name=project_name,
            home_root=entities.HomeRootConfig(
                snippets=[s.strip() for s in snippets if s.strip()],
            ),
            project_root=entities.ProjectSpecificConfig(
                dao_output_config=(
                    [
                        entities.CodeGenOutputConfig(
                            directory=dao_dir.split(","),
                            language=typing.cast(
                                entities.SupportedLanguagesValues, dao_prog_lang
                            ),
                        )
                    ]
                    if dao_dir and dao_prog_lang
                    else []
                ),
                dto_output_config=(
                    [
                        entities.CodeGenOutputConfig(
                            directory=dto_dir.split(","),
                            language=typing.cast(
                                entities.SupportedLanguagesValues, dto_prog_lang
                            ),
                        )
                    ]
                    if dto_dir and dto_prog_lang
                    else []
                ),
                api_output_config=(
                    [
                        entities.CodeGenOutputConfig(
                            directory=api_dir.split(","),
                            language=typing.cast(
                                entities.SupportedLanguagesValues, api_prog_lang
                            ),
                        )
                    ]
                    if api_dir and api_prog_lang
                    else []
                ),
                test_services_output_directory=(
                    test_services_dir.split(",") if test_services_dir else []
                ),
                test_api_output_config=(
                    [
                        entities.CodeGenOutputConfig(
                            directory=test_routes_dir.split(","),
                            language=typing.cast(
                                entities.SupportedLanguagesValues, test_api_prog_lang
                            ),
                        )
                    ]
                    if test_routes_dir and test_api_prog_lang
                    else []
                ),
                adapters_output_directory=(
                    adapter_dir.split(",") if adapter_dir else []
                ),
                use_cases_output_directory=(
                    use_cases_dir.split(",") if use_cases_dir else []
                ),
                app_definition_directory=(
                    app_definition_dir.split(",") if app_definition_dir else []
                ),
                contract_sync_output_config=(
                    (
                        [
                            entities.ContractSyncOutputConfig(
                                source_language="python",
                                output_directory=contract_sync_python_output_dir.split(
                                    ","
                                ),
                            )
                        ]
                        if contract_sync_python_output_dir
                        else []
                    )
                    + (
                        [
                            entities.ContractSyncOutputConfig(
                                source_language="typescript",
                                output_directory=contract_sync_typescript_output_dir.split(
                                    ","
                                ),
                            )
                        ]
                        if contract_sync_typescript_output_dir
                        else []
                    )
                ),
            ),
        )

        file_io.File("specs", "project_config.json").write_json(
            project_config.model_dump()
        )
        logging.info("Configured project %s", project_name)
        return project_config
