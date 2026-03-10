import devOS.use_cases.code_gen.dao.generate_python_dao as py_dao_gen
import devOS.use_cases.code_gen.dtos.generate_python_dtos as py_dto_gen
import devOS.use_cases.code_gen.dtos.generate_typescript_dtos as ts_dto_gen
import devOS.use_cases.code_gen.endpoints.generate_python_endpoints as py_endpoint_gen
import devOS.use_cases.code_gen.tests.generate_python_tests as py_tests_gen
from devOS.use_cases.utils.file_io import File
from devOS.domain import entities
import os
from git import Repo


class GenerateCodeUseCase:
    """Generate code artifacts from project specifications.

    This use case reads DAO and endpoint specs, generates Python/TypeScript
    code artifacts, and writes them to the configured project paths.

    Attributes
    ----------
    dao_spec_path : list[str]
        Path components pointing to the DAO spec JSON file.
    dao_output_path : list[str]
        Path components for the generated DAO output file.
    endpoints_spec_path : list[str]
        Path components pointing to the endpoints spec JSON file.
    dto_output_path : list[str]
        Path components for the generated DTO output file.
    endpoints_output_path : list[str]
        Path components for the generated endpoints output file.
    tests_output_path_endpoints : list[str]
        Path components for the generated endpoints test file.
    services_output_path : list[list[str]]
        Path components for each service output file.
    tests_output_path_services : list[str]
        Path components for the generated services test file.
    """

    def __init__(self, project_structure: entities.ProjectConfigSchema):
        """Initialize generator paths from the project configuration.

        Parameters
        ----------
        project_structure : entities.ProjectConfigSchema
            Project configuration defining the root and backend paths.
        """
        self.dao_spec_path = ["specs", "dao_spec.json"]
        self.endpoints_spec_path = ["specs", "endpoints_spec.json"]
        self.project_structure = project_structure

        # Flatten the list of lists for services_output_path and tests_output_path_services
        self.services_output_path = self.__search_for_services()
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

    def __search_for_services(self) -> list[str]:
        # walk through the file system start from the src directory to find
        # all the files containing @service string
        services = []
        for dirpath, dirnames, filenames in os.walk("src"):
            for filename in filenames:
                if filename.endswith(".py"):
                    file_path = os.path.join(dirpath, filename)
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        if "@service" in content:
                            services.append(file_path)

        return services

    def __write_code(self, path_parts: list[str], code: str) -> None:

        adapters_output_dir = (
            self.project_structure.project_root.adapters_output_directory
        )
        use_cases_output_dir = (
            self.project_structure.project_root.use_cases_output_directory
        )
        python_dao_output_dir = list(
            filter(
                lambda item: item.language == "python",
                self.project_structure.project_root.dao_output_config,
            )
        )[0]
        python_dto_output_dir = list(
            filter(
                lambda item: item.language == "python",
                self.project_structure.project_root.dto_output_config,
            )
        )[0]
        python_api_output_dir = list(
            filter(
                lambda item: item.language == "python",
                self.project_structure.project_root.api_output_config,
            )
        )[0]
        updated_code = (
            code.replace(
                "project_name.infrastructure.adapters",
                ".".join(adapters_output_dir).replace("src.", "").replace(".py", ""),
            )
            .replace(
                "project_name.infrastructure.app",
                ".".join(self.project_structure.project_root.app_definition_directory)
                .replace("src.", "")
                .replace(".py", ""),
            )
            .replace(
                "project_name.use_cases.use_cases",
                ".".join(use_cases_output_dir).replace("src.", "").replace(".py", ""),
            )
            .replace(
                "project_name.domain.dao",
                ".".join(python_dao_output_dir.directory)
                .replace("src.", "")
                .replace(".py", ""),
            )
            .replace(
                "project_name.use_cases.dto",
                ".".join(python_dto_output_dir.directory)
                .replace("src.", "")
                .replace(".py", ""),
            )
            .replace(
                "project_name.infrastructure.routes",
                ".".join(python_api_output_dir.directory)
                .replace("src.", "")
                .replace(".py", ""),
            )
            .replace("project_name", self.project_name)
        )

        File(*path_parts).write(updated_code)

    def generate_dao(
        self,
        project_name: str,
    ) -> None:
        """Generate DAO code from the DAO specification."""
        self.project_name = project_name
        specs = File(*self.dao_spec_path).get_json()

        for dao_output_configs in self.project_structure.project_root.dao_output_config:
            if dao_output_configs.language == "python":
                # generate imports
                final_code = py_dao_gen.generate_code_header()

                # Generate all enums
                enums_code = py_dao_gen.generate_all_enums_code(
                    [entities.DAOSchemaSpec.model_validate(spec) for spec in specs]
                )
                if enums_code:
                    final_code += enums_code + "\n"

                for raw_spec in specs:
                    spec = entities.DAOSchemaSpec.model_validate(raw_spec)
                    final_code += py_dao_gen.generate_dao_code(spec) + "\n"

                self.__write_code(dao_output_configs.directory, final_code)

                # generate data association tables if any
                dao_filename = dao_output_configs.directory[-1]
                assoc_dao_code = py_dao_gen.generate_association_dao_header()
                assoc_dao_code += py_dao_gen.generate_all_association_tables(
                    [entities.DAOSchemaSpec.model_validate(spec) for spec in specs]
                ).replace(
                    "import project_name.domain.association_dao",
                    f"import {self.project_name}.domain.association_{dao_filename.replace('.py','')}",
                )

                self.__write_code(
                    dao_output_configs.directory[:-1] + [f"association_{dao_filename}"],
                    assoc_dao_code,
                )

                # generate python use_cases for the daos generated
                default_python_use_cases = File(
                    os.path.dirname(__file__),
                    "templates",
                    "python_use_cases.py",
                ).read_as_utf8()
                self.__write_code(
                    self.project_structure.project_root.use_cases_output_directory[:-1]
                    + ["crud_use_cases.py"],
                    default_python_use_cases,
                )

                # add associated tests
                tests_for_use_cases = File(
                    os.path.dirname(__file__),
                    "templates",
                    "test_use_cases.py",
                ).read_as_utf8()
                self.__write_code(
                    ["tests", "test_crud_use_cases.py"], tests_for_use_cases
                )

                # generate python adapter for the daos generated
                default_python_adapter = File(
                    os.path.dirname(__file__),
                    "templates",
                    "python_adapter.py",
                ).read_as_utf8()

                self.__write_code(
                    self.project_structure.project_root.adapters_output_directory[:-1]
                    + ["sqlalchemy_db_adapter.py"],
                    default_python_adapter,
                )

                # add associated tests
                tests_for_adapter = File(
                    os.path.dirname(__file__),
                    "templates",
                    "test_adapters.py",
                ).read_as_utf8()
                self.__write_code(
                    ["tests", "test_sqlalchemy_db_adapter.py"], tests_for_adapter
                )

            else:
                print(
                    f"DAO generation for language {dao_output_configs.language} is not supported yet."
                )

    def generate_dto(
        self,
        project_name: str,
    ) -> None:
        """Generate DTO code from endpoint and DAO specifications."""
        self.project_name = project_name
        endpoints_raw = File(*self.endpoints_spec_path).get_json()
        endpoints_spec = entities.EndpointsSpec.model_validate(endpoints_raw)

        dao_raw = File(*self.dao_spec_path).get_json()
        dao_specs = [entities.DAOSchemaSpec.model_validate(d) for d in dao_raw]

        for dto_output_configs in self.project_structure.project_root.dto_output_config:
            if dto_output_configs.language == "python":
                # generate python dto code for custom endpoints
                py_dt_output = py_dto_gen.generate_dto_code(endpoints_spec, dao_specs)
                print("Python DTO code generated:\n")
                print(py_dt_output)
                self.__write_code(dto_output_configs.directory, py_dt_output)

                # generate python dto code for crud endpoints
                py_crud_dto_output = py_dto_gen.generate_dao_dtos_file(dao_specs)
                print("Python CRUD DTO code generated:\n")
                print(py_crud_dto_output)
                self.__write_code(
                    dto_output_configs.directory[:-1] + ["crud_dto.py"],
                    py_crud_dto_output,
                )

                # generate the python app definition file
                app_definition_code = py_endpoint_gen.generate_app_definition_code(
                    self.project_name
                )
                print("Python App Definition code generated:\n")
                print(app_definition_code)
                self.__write_code(
                    self.project_structure.project_root.app_definition_directory,
                    app_definition_code,
                )

            elif dto_output_configs.language == "typescript":
                ts_dto_output = "import { z } from 'zod';\n\n"

                # generate typescript dto code for each dao
                for dao_spec in dao_specs:
                    ts_dto_output += ts_dto_gen.generate_dtos_for_dao(dao_spec)

                # generate typescript dto code for custom endpoints
                ts_dto_output += ts_dto_gen.generate_custom_endpoint_schemas(
                    endpoints_spec
                )
                print("TypeScript DTO code generated:\n")
                print(ts_dto_output)
                self.__write_code(dto_output_configs.directory, ts_dto_output)
            else:
                print(
                    f"DTO generation for language {dto_output_configs.language} is not supported yet."
                )

    def generate_endpoints(
        self,
        project_name: str,
    ) -> None:
        """Generate FastAPI endpoints from specifications."""
        self.project_name = project_name
        endpoints_raw = File(*self.endpoints_spec_path).get_json()
        endpoints_spec = entities.EndpointsSpec.model_validate(endpoints_raw)

        dao_raw = File(*self.dao_spec_path).get_json()
        dao_specs = [entities.DAOSchemaSpec.model_validate(d) for d in dao_raw]

        for api_output_configs in self.project_structure.project_root.api_output_config:
            if api_output_configs.language != "python":
                print(
                    f"Endpoint generation for language {api_output_configs.language} is not supported yet."
                )
                continue

            # generate python endpoint code.
            endpoints_code = py_endpoint_gen.generate_endpoints_code(
                endpoints_spec, dao_specs
            )
            print("Generated Endpoints Code:\n", endpoints_code)
            if len(endpoints_spec.endpoints.keys()) > 0:
                endpoints_code = py_endpoint_gen.generate_endpoints_code(
                    endpoints_spec, dao_specs
                )
                print("Generated Endpoints Code:\n", endpoints_code)
                self.__write_code(api_output_configs.directory, endpoints_code)

            # generate crud endpoints code
            crud_endpoints_code = py_endpoint_gen.generate_crud_endpoints_file(
                dao_specs
            )
            print("Generated CRUD Endpoints Code:\n", crud_endpoints_code)
            self.__write_code(
                api_output_configs.directory[:-1] + ["crud_routes.py"],
                crud_endpoints_code,
            )

    def generate_tests_for_endpoints(
        self,
        project_name: str,
    ) -> None:
        """Generate pytest tests for generated endpoints."""
        self.project_name = project_name
        generator = py_tests_gen.GenerateTestsUseCase()
        for index, test_api_output_configs in enumerate(
            self.project_structure.project_root.test_api_output_config
        ):
            if test_api_output_configs.language != "python":
                print(
                    f"Test generation for language {test_api_output_configs.language} is not supported yet."
                )
                continue

            corresponding_api_path = (
                self.project_structure.project_root.api_output_config[index].directory
            )
            generated_api_code = File(*corresponding_api_path).read_as_utf8()
            print(f"Generating tests for {corresponding_api_path}...")
            result = generator.generate_tests_for_file(
                generated_api_code, file_type="endpoint"
            )
            print("Generated test code:")
            print(result)
            print("Writing tests to:", test_api_output_configs.directory)
            self.__write_code(test_api_output_configs.directory, result or "")

    def generate_tests_for_services(
        self,
        project_name: str,
    ) -> None:
        """Generate pytest tests for generated services."""
        self.project_name = project_name
        result = ""
        generator = py_tests_gen.GenerateTestsUseCase()
        service_tests_output_path = (
            self.project_structure.project_root.test_services_output_directory
        )
        for service_path in self.services_output_path:
            code = File(service_path).read_as_utf8()
            print("Generating tests for generated_services.py...")
            print(code)
            # NOTE: in the future add also option file extension to determing programming language to use.
            code_generated = generator.generate_tests_for_file(
                code, file_type="usecase"
            )
            if code_generated is not None:
                result += code_generated + "\n"
            print("Generated test code:")
            print(result)
            print("Writing tests to:", service_tests_output_path)
            self.__write_code(
                service_tests_output_path + [f"test_{os.path.basename(service_path)}"],
                result or "",
            )

    def execute(self, project_name: str | None = None) -> None:
        """Run all generation steps in sequence.
        1. Generate DAOs
        2. Generate DTOs
        3. Generate Endpoints
        4. Generate Tests for Endpoints
        5. Generate Tests for Services

        Parameters
        ----------
        project_name : str
            Name of the project to be used in generated code imports.

        Example
        -------
        dev build my_project
        """
        if project_name is not None:
            self.project_name = project_name

        # execute all the code generation steps one after another
        self.generate_dao(self.project_name)
        self.generate_dto(self.project_name)
        self.generate_endpoints(self.project_name)
        self.generate_tests_for_endpoints(self.project_name)
        self.generate_tests_for_services(self.project_name)


if __name__ == "__main__":
    project_structure_spec = File("specs", "project_config.json").get_json()
    project_structure = entities.ProjectConfigSchema(**project_structure_spec)
    code_generator = GenerateCodeUseCase(project_structure=project_structure)
    code_generator.execute("my_project")
