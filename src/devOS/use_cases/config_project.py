from __future__ import annotations
import typing
from colorama import Fore, Style, init as colorama_init  # type: ignore
from devOS.domain import entities
from devOS.use_cases.utils.file_io import File
from devOS.use_cases import use_cases
import os
from git import Repo


class ConfigProjectUseCase(use_cases.OSInterface):

    def __init__(self) -> None:
        super().__init__(os.getcwd())
        # this is useful if the config already exists but the user wants to update it through the wizard.
        self.update_existing_config = False
        colorama_init(autoreset=True)
        self.project_name = self._extract_git_repo_name()

    def _extract_git_repo_name(self) -> str:
        """
        Extract the project name from the git repository name.

        Returns
        -------
        str
            The git repository name, or fallback to directory name.
        """
        try:
            repo = Repo(".", search_parent_directories=True)
            # Get the repo name from the repository URL or directory
            repo_name = repo.remote().url.split("/")[-1].replace(".git", "")
            return repo_name if repo_name else os.path.basename(os.getcwd())
        except Exception:
            # Fallback to directory name if git repo not found
            try:
                return os.path.basename(os.getcwd())
            except Exception:
                return "project_name"

    def _validate_choice(self, allowed: set[str]) -> typing.Callable[[str], None]:
        allowed_lower = {a.lower() for a in allowed}

        def _inner(value: str) -> None:
            if value.lower() not in allowed_lower:
                raise ValueError(f"must be one of: {', '.join(sorted(allowed))}")

        return _inner

    def _parse_list(self, raw: str) -> list[str]:
        """
        Parse comma-separated list:  "a, b, c" -> ["a", "b", "c"]
        Empty -> []
        """
        raw = (raw or "").strip()
        if not raw:
            return []
        return [x.strip() for x in raw.split(",") if x.strip()]

    def _prompt_list(self, label: str, default: str = "") -> list[str]:
        raw = self.__prompt(label + " (comma-separated)", default=default)
        return self._parse_list(raw)

    def _parse_services(self, raw: str) -> list[list[str]]:
        """
        Parse service groups:
        "svcA,svcB; svcC" -> [["svcA","svcB"], ["svcC"]]
        Semicolon separates groups; commas separate services within a group.
        Empty -> []
        """
        raw = (raw or "").strip()
        if not raw:
            return []
        groups: list[list[str]] = []
        for g in raw.split(";"):
            services = [s.strip() for s in g.split(",") if s.strip()]
            if services:
                groups.append(services)
        return groups

    def _prompt_services(self, label: str, default_raw: str = "") -> list[list[str]]:
        hint = " (groups separated by ';' and items by ',')"
        raw = self.__prompt(label + hint, default=default_raw)
        return self._parse_services(raw)

    def __display_devOS_banner(self) -> None:
        # Squared terminal symbol: ▣
        banner = r"""
    ▣  devOS CONFIG WIZARD  ▣
    """
        quote = "“Quality is not an act, it is a habit.” — Aristotle"
        vibe = f"{quote}\n\n(😼 - devOS) 🧩  Compose.  🤖  Generate.  💻  Deploy.\n"

        print(Fore.GREEN + Style.BRIGHT + banner + Style.RESET_ALL, end="")
        print(Fore.GREEN + vibe + Style.RESET_ALL)

    def __prompt(
        self,
        label: str,
        default: typing.Optional[str] = None,
        validator: typing.Optional[typing.Callable[[str], None]] = None,
    ) -> str:
        while True:
            suffix = f" [{default}]" if default not in (None, "") else ""
            raw = input(f"{label}{suffix}: ").strip()

            value = raw if raw else (default or "")
            if value == "":
                print("  Please enter a value.")
                continue

            try:
                if validator is not None:
                    validator(value)
            except ValueError as exc:
                print(f"  Invalid value: {exc}")
                continue

            return value

    def __prompt_optional(
        self, label: str, default: typing.Optional[str] = None
    ) -> typing.Optional[str]:
        suffix = f" [{default}]" if default not in (None, "") else ""
        raw = input(f"{label}{suffix} (leave blank to skip): ").strip()
        if raw:
            return raw
        return default if default else None

    def __run_setup_wizard(self, project_name: str) -> entities.ProjectConfigSchema:

        self.__display_devOS_banner()

        self.log_message("Let's set up your project configuration step by step.\n")
        self.log_message(
            "You can press Enter to accept the default value shown in [brackets].\n"
        )

        def get_default(path, fallback=""):
            """Helper to get a nested value from existing_config or fallback."""
            val = None
            if self.update_existing_config:
                val = File("specs", "project_config.json").get_json()
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
        self.log_message(
            "The following information is used to manage vaults and snippets\n"
        )
        vault = self.__prompt(
            "Enter the vault directory (relative to home, comma-separated)",
            default=get_default(
                ["home_root", "vault"], "protocol,00 PKM,3 Resources,Vault"
            ),
        ).split(",")

        snippets = self.__prompt(
            "Enter the snippets directory (relative to home, comma-separated)",
            default=get_default(["home_root", "snippets"], "protocol,devOS,snippets"),
        ).split(",")

        # Prompt for project_root directories
        self.log_message(
            "The following information is used to configure code generation outputs\n"
        )
        dao_dir = self.__prompt_optional(
            "Enter the Data Access Object (DAO) output directory (relative to project root)",
            default=get_default(
                ["project_root", "dao_output_config", 0, "directory"],
                f"src,{project_name},domain,dao.py",
            ),
        )
        dto_dir = self.__prompt_optional(
            "Enter the Data Transfer Object (DTO) output directory (relative to project root)",
            default=get_default(
                ["project_root", "dto_output_config", 0, "directory"],
                f"src,{project_name},use_cases,dto.py",
            ),
        )
        api_dir = self.__prompt_optional(
            "Enter the API endpoints output directory (relative to project root)",
            default=get_default(
                ["project_root", "api_output_config", 0, "directory"],
                f"src,{project_name},infrastructure,routes.py",
            ),
        )
        test_services_dir = self.__prompt_optional(
            "Enter the test services output directory (relative to project root)",
            default=get_default(
                ["project_root", "test_services_output_directory", 0, "directory"],
                "tests",
            ),
        )
        test_routes_dir = self.__prompt_optional(
            "Enter the test routes output directory (relative to project root) ensure the index matches the api output directory!",
            default=get_default(
                ["project_root", "test_api_output_config", 0, "directory"],
                "tests,test_crud_routes.py",
            ),
        )

        adapter_dir = self.__prompt_optional(
            "Enter the adapters output directory (relative to project root)",
            default=get_default(
                ["project_root", "adapter_output_directory", 0, "directory"],
                f"src,{project_name},infrastructure,sqlalchemy_db_adapter.py",
            ),
        )

        use_cases_dir = self.__prompt_optional(
            "Enter the use cases output directory (relative to project root)",
            default=get_default(
                ["project_root", "use_cases_output_directory", 0, "directory"],
                f"src,{project_name},use_cases,crud_use_cases.py",
            ),
        )
        app_definition_dir = self.__prompt_optional(
            "Enter the app definition directory (relative to project root)",
            default=get_default(
                ["project_root", "app_definition_directory", 0, "directory"],
                f"src,{project_name},infrastructure,app.py",
            ),
        )

        dao_prog_lang = self.__prompt_optional(
            "Enter the programming language for DAO generation",
            default=get_default(
                ["project_root", "dao_output_config", 0, "language"], "python"
            ),
        )
        dto_prog_lang = self.__prompt_optional(
            "Enter the programming language for DTO generation",
            default=get_default(
                ["project_root", "dto_output_config", 0, "language"], "python"
            ),
        )
        api_prog_lang = self.__prompt_optional(
            "Enter the programming language for API endpoints generation ensure the index matches the api output directory!",
            default=get_default(
                ["project_root", "api_output_config", 0, "language"], "python"
            ),
        )
        test_api_prog_lang = self.__prompt_optional(
            "Enter the programming language for test routes generation",
            default=get_default(
                ["project_root", "test_api_output_config", 0, "language"], "python"
            ),
        )

        # Build the project configuration
        project_config = entities.ProjectConfigSchema(
            home_root=entities.HomeRootConfig(
                vault=[v.strip() for v in vault if v.strip()],
                snippets=[s.strip() for s in snippets if s.strip()],
            ),
            project_root=entities.ProjectSpecificConfig(
                dao_output_config=(
                    [
                        entities.CodeGenOutputConfig(
                            directory=dao_dir.split(","),
                            language=dao_prog_lang,  # type: ignore
                        )
                    ]
                    if dao_dir and dao_prog_lang
                    else []
                ),
                dto_output_config=(
                    [
                        entities.CodeGenOutputConfig(
                            directory=dto_dir.split(","),
                            language=dto_prog_lang,  # type: ignore
                        )
                    ]
                    if dto_dir and dto_prog_lang
                    else []
                ),
                api_output_config=(
                    [
                        entities.CodeGenOutputConfig(
                            directory=api_dir.split(","),
                            language=api_prog_lang,  # type: ignore
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
                            language=test_api_prog_lang,  # type: ignore
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
            ),
        )

        return project_config

    def set_update_existing_config(self) -> ConfigProjectUseCase:
        self.update_existing_config = True
        return self

    def initial_setup(self):
        os.system("cd frontend && npm install")
        os.system("npm install -g @openai/codex")

    def write_project_config(
        self, cfg: entities.ProjectConfigSchema, update_existing_config: bool = False
    ) -> None:
        """Write the project configuration to `specs/project_config.json`.

        Parameters
        ----------
        cfg : entities.ProjectConfigSchema
            The project configuration to write.
        update_existing_config : bool, optional
            Whether to update an existing configuration file, by default False.
        """
        print(
            Fore.GREEN
            + Style.BRIGHT
            + f"\n▣ Final Config {cfg.model_dump_json(indent=4)}\n"
            + Style.RESET_ALL
        )
        # save the config to specs/project_config.json
        File("specs", "project_config.json").write_json(cfg.model_dump())
        if update_existing_config is False:
            File("specs", "dao_spec.json").write_json([])

            File("specs", "endpoints_spec.json").write_json(
                {
                    "title": "Items Collection CRUD Application",
                    "version": "1.0.0",
                    "description": "Endpoints for creating updating and deleting items from a collection.",
                    "include_relationship_endpoints": True,
                    "endpoints": {
                        "collection": [],
                        "item": [
                            {
                                "name": "read_items_by_collection",
                                "description": "Retrieve a list of all items within a specified collection.",
                                "method": "GET",
                                "version": "v1",
                                "path": "collections/{collection_id}/items",
                                "request_schema": {
                                    "collection_id": {
                                        "type": "string",
                                        "description": "The unique identifier of the collection whose items are to be retrieved.",
                                        "required": True,
                                        "parse_value_from_path": True,
                                    }
                                },
                                "response_schema": {
                                    "items": {
                                        "type": "dao",
                                        "name": "Item",
                                        "is_list": True,
                                    }
                                },
                                "use_case": {
                                    "name": "QueryUseCase",
                                    "method": "read_items_by_collection",
                                },
                            }
                        ],
                    },
                }
            )

    def _get_default_config(self, project_name: str) -> entities.ProjectConfigSchema:
        """
        Generate a default project configuration.

        Parameters
        ----------
        project_name : str
            Name of the project to use in the configuration.

        Returns
        -------
        entities.ProjectConfigSchema
            Default project configuration.
        """
        return entities.ProjectConfigSchema(
            home_root=entities.HomeRootConfig(
                vault=["protocol", "00 PKM", "3 Resources", "Vault"],
                snippets=["protocol", "devOS", "snippets"],
            ),
            project_root=entities.ProjectSpecificConfig(
                dao_output_config=[
                    entities.CodeGenOutputConfig(
                        directory=["src", project_name, "domain", "dao.py"],
                        language="python",
                    )
                ],
                dto_output_config=[
                    entities.CodeGenOutputConfig(
                        directory=["src", project_name, "use_cases", "dto.py"],
                        language="python",
                    )
                ],
                api_output_config=[
                    entities.CodeGenOutputConfig(
                        directory=["src", project_name, "infrastructure", "routes.py"],
                        language="python",
                    )
                ],
                test_services_output_directory=["tests"],
                test_api_output_config=[
                    entities.CodeGenOutputConfig(
                        directory=["tests", "test_crud_routes.py"],
                        language="python",
                    )
                ],
                adapters_output_directory=[
                    "src",
                    project_name,
                    "infrastructure",
                    "sqlalchemy_db_adapter.py",
                ],
                use_cases_output_directory=[
                    "src",
                    project_name,
                    "use_cases",
                    "crud_use_cases.py",
                ],
                app_definition_directory=[
                    "src",
                    project_name,
                    "infrastructure",
                    "app.py",
                ],
            ),
        )

    def execute(
        self, project_name: typing.Optional[str] = None
    ) -> entities.ProjectConfigSchema:
        """Build project configuration.

        If a configuration file exists, loads it. Otherwise, returns a default
        configuration in memory without writing files.

        Parameters
        ----------
        project_name : str, optional
            Name of the project. If not provided, will be extracted from git repository.

        Returns
        -------
        entities.ProjectConfigSchema
            The constructed project configuration.

        Side Effects
        ------------
        Creates or updates the `specs/project_config.json` file only when
        configuration is explicitly updated through the setup wizard.
        """
        if project_name is None:
            project_name = self.project_name
        if (
            File("specs", "project_config.json").exists() is False
            and not self.update_existing_config
        ):
            # Return a default config in memory only.
            # Persisting to disk is done only through `dev config`.
            cfg = self._get_default_config(project_name)
            return cfg
        elif self.update_existing_config:
            # Run wizard only when explicitly requested
            cfg = self.__run_setup_wizard(project_name)
            self.write_project_config(cfg)
        else:
            cfg_metadata = File("specs", "project_config.json").get_json()
            try:
                cfg = entities.ProjectConfigSchema.model_validate(cfg_metadata)
            except Exception as e:
                print(e)
                print(
                    "Existing configuration is invalid. Running the setup wizard again."
                )
                cfg = self.__run_setup_wizard(project_name)

                self.write_project_config(cfg, update_existing_config=True)

        return cfg
