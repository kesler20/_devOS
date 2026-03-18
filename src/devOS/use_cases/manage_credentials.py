from devOS.use_cases.utils.file_io import File
import os
import pyperclip  # type: ignore
from devOS.use_cases import use_cases


class ManageCredentialsUseCase(use_cases.OSInterface):
    """Manage project credentials stored in a local vault.

    Attributes
    ----------
    vault_dir : str
        Absolute path to the credentials vault directory.
    root_dir : str
        Absolute path to the project root directory.
    directory : str
        Current working directory at initialization time.
    """

    def __init__(self, credentials_vault: list[str], root_dir: list[str]):
        """Initialize the credential manager.

        Parameters
        ----------
        credentials_vault : list[str]
            Path components for the vault directory under the user's home.
        root_dir : list[str]
            Path components for the project root under the user's home.
        """
        super().__init__(os.getcwd())
        self.vault_dir = os.path.join(os.path.expanduser("~"), *credentials_vault)

    def _generate_masked_env_example(self, dotenv_content: str) -> str:
        """Generate a masked .env.example from .env content.

        Keeps all keys and comments but replaces all values with empty strings.

        Parameters
        ----------
        dotenv_content : str
            The full content of the .env file.

        Returns
        -------
        str
            Masked content suitable for .env.example.
        """
        masked_lines = []
        for line in dotenv_content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped == "":
                masked_lines.append(line)
            elif "=" in line:
                key = line.split("=", 1)[0]
                masked_lines.append(f"{key}=")
            else:
                masked_lines.append(line)
        return "\n".join(masked_lines)

    def set_credentials(self, project_name: str):
        """Store project .env in the vault and write a masked .env.example locally.

        Reads the current .env file, saves it to the vault, then generates a
        masked copy (all values stripped) and writes it both to the project
        directory as .env.example and to the vault.

        Parameters
        ----------
        project_name : str
            Project name used to namespace stored files.
        """
        self.log_message(f"Reading .env from {self.directory}")
        dotenv_content = File(".env").read_as_utf8()

        dotenv_example_content = self._generate_masked_env_example(dotenv_content)

        self.log_message("Writing masked .env.example to project directory")
        File(".env.example").write_as_utf8(dotenv_example_content)

        self.log_message(
            f"Writing .env to vault at {os.path.join(self.vault_dir, project_name, f'dotenv_{project_name}.txt')}"
        )
        File(
            self.vault_dir, "dotenv", project_name, f"dotenv_{project_name}.txt"
        ).write(dotenv_content)
        self.log_message(
            f"Writing .env.example to vault at {os.path.join(self.vault_dir, project_name, f'dotenv_example_{project_name}.txt')}"
        )
        File(
            self.vault_dir, "dotenv", project_name, f"dotenv_example_{project_name}.txt"
        ).write(dotenv_example_content)

    def get_credentials(self, project_name: str):
        """Restore project .env files from the credentials vault.

        Parameters
        ----------
        project_name : str
            Project name used to locate stored files.
        """
        self.log_message(f"Reading credentials from vault for project '{project_name}'")
        dotenv_content = File(
            self.vault_dir, "dotenv", project_name, f"dotenv_{project_name}.txt"
        ).read_as_utf8()
        dotenv_example_content = File(
            self.vault_dir, "dotenv", project_name, f"dotenv_example_{project_name}.txt"
        ).read_as_utf8()

        self.log_message(f"Writing .env to {self.directory}")
        File(".env").write(dotenv_content)
        self.log_message(f"Writing .env.example to {self.directory}")
        File(".env.example").write(dotenv_example_content)

    def set_global_secret(self, secret_key: str, secret_value: str):
        """Store a global secret in the vault.

        Parameters
        ----------
        secret_key : str
            Key used to store the secret.
        secret_value : str
            Secret value to write.
        """
        self.log_message(
            f"Writing global secret '{secret_key}' to vault at {os.path.join(self.vault_dir, f'global_secret_{secret_key}.txt')}"
        )
        File(self.vault_dir, "secrets", f"global_secret_{secret_key}.txt").write(
            secret_value
        )

    def get_global_secret(self, secret_key: str):
        """Retrieve a global secret and copy it to the clipboard.

        Parameters
        ----------
        secret_key : str
            Key used to locate the secret.
        """
        self.log_message(
            f"Reading global secret '{secret_key}' from vault at {os.path.join(self.vault_dir, f'global_secret_{secret_key}.txt')}"
        )
        secret = File(
            self.vault_dir, "secrets", f"global_secret_{secret_key}.txt"
        ).read_as_utf8()
        self.log_message(f"Secret value: {secret}")
        pyperclip.copy(secret)
        self.log_message("Secret copied to clipboard.")
