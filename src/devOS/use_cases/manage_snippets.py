from devOS.use_cases.utils.file_io import File
from devOS.use_cases.use_cases import OSInterface
from devOS.use_cases.manage_git_repo import ManageGitRepositoryUseCase
import os
import pyperclip  # type: ignore
from devOS.use_cases import use_cases
from random import randint
import shutil


class ManageSnippetsUseCase:
    """Manage code snippets stored in a git-backed repository.

    Snippets are stored in a directory structure and can be added, updated,
    retrieved, or deleted. Each snippet is identified by a unique `snippet_id`.

    Attributes
    ----------
    snippets_repository : str
        Absolute path to the snippets repository root.
    """

    def __init__(
        self,
        *snippets_repository,
    ):
        """Initialize the snippets repository location.

        Parameters
        ----------
        *snippets_repository : str
            Path components to the repository under the user's home directory.
        """
        home_dir = os.path.expanduser("~")
        if len(snippets_repository) == 0:
            raise ValueError("snippets_repository must be provided.")
        if len(snippets_repository) == 1:
            self.snippets_repository = os.path.join(home_dir, snippets_repository[0])
        else:
            self.snippets_repository = os.path.join(home_dir, *snippets_repository)
        # check if the snippets repository exists.
        if not os.path.exists(self.snippets_repository):
            raise FileNotFoundError(
                f"Snippets repository not found: {self.snippets_repository}"
            )

    def __push_commit(self, commit_message: str):
        # style the commit message
        code_commit_message_emojis = ["😕", "⭐", "✊", "🤝", "👐"]
        message_suffix = code_commit_message_emojis[
            randint(0, len(code_commit_message_emojis) - 1)
        ]
        styled_commit_message = commit_message + message_suffix

        with use_cases.OSInterface(self.snippets_repository) as osi:
            osi.execute_command("git pull")
            osi.execute_command("git add .")
            osi.execute_command(f'git commit -m "{styled_commit_message}"')
            osi.execute_command("git push")
            print("\nnew commit pushed successfully ✨\n", styled_commit_message)

    def __copy_directory(self, source_dir: str, destination_dir: str) -> list[str]:
        """
        Copy files from a source folder to a destination folder.

        Parameters
        ----------
        source_dir : str
            Absolute or relative path to the source directory.
        destination_dir : str
            Absolute or relative path to the destination directory.

        Returns
        -------
        list[str]
            Relative file paths that were copied.
        """
        if not os.path.isdir(source_dir):
            raise FileNotFoundError(f"Source directory not found: {source_dir}")

        os.makedirs(destination_dir, exist_ok=True)
        copied_files: list[str] = []

        for root, _, files in os.walk(source_dir):
            relative_root = os.path.relpath(root, source_dir)
            for filename in files:
                relative_path = (
                    filename
                    if relative_root == "."
                    else os.path.join(relative_root, filename)
                )
                source_file = os.path.join(root, filename)
                destination_file = os.path.join(destination_dir, relative_path)
                os.makedirs(os.path.dirname(destination_file), exist_ok=True)
                shutil.copy2(source_file, destination_file)
                copied_files.append(relative_path)

        return copied_files

    def set(
        self,
        from_key: str,
        snippet_source_dir: str,
        to_key: str,
        snippet_destination_dir: str,
    ):
        """Example usage:

        dev set snippet from path,to,local,snippet.txt to snippet_repo_dir,subdir,snippet_id

        if you want to copy from clipboard:
        dev set snippet from clipboard to snippet_repo_dir,subdir,snippet_id
        """
        ignore = from_key
        ignore = to_key
        # get the source content from the clipboard or from the source file.
        if snippet_source_dir == "clipboard":
            source_file_content = pyperclip.paste()
        else:
            source_file_content = File(*snippet_source_dir.split(",")).read_as_utf8()

        snippet_id = snippet_source_dir.split(",")[-1]

        # write the source content to the snippet destination.
        File(
            self.snippets_repository, *snippet_destination_dir.split(",")
        ).write_as_utf8(source_file_content)

        # commit the changes to the git repository.
        self.__push_commit(f"feat: added {snippet_id} to {snippet_destination_dir}")

    def set_folder(
        self,
        from_key: str,
        snippet_source_dir: str,
        to_key: str,
        snippet_destination_dir: str,
    ):
        """
        Store a folder of snippets in the snippets repository.

        Parameters
        ----------
        from_key : str
            Placeholder for the "from" keyword.
        snippet_source_dir : str
            Comma-separated path to the local folder to copy.
        to_key : str
            Placeholder for the "to" keyword.
        snippet_destination_dir : str
            Comma-separated path inside the snippets repository.

        Examples
        --------
        dev set snippet folder from path,to,local,folder to snippet_repo_dir,subdir
        """
        ignore = from_key
        ignore = to_key

        if snippet_source_dir == "clipboard" or snippet_destination_dir == "clipboard":
            raise ValueError("clipboard is not supported for folder snippets.")

        source_dir = os.path.join(*snippet_source_dir.split(","))
        destination_dir = os.path.join(
            self.snippets_repository, *snippet_destination_dir.split(",")
        )

        self.__copy_directory(source_dir, destination_dir)

        snippet_id = os.path.basename(os.path.normpath(source_dir))
        self.__push_commit(
            f"feat: added folder {snippet_id} to {snippet_destination_dir}"
        )

    def get(
        self,
        from_key: str,
        snippet_source_dir: str,
        to_key: str,
        snippet_destination_dir: str,
    ):
        """Example usage:

        dev get snippet from snippet_repo_dir,subdir,snippet_id to clipboard

        or
        dev get snippet from snippet_repo_dir,subdir,snippet_id to path,to,local,snippet.txt
        """
        ignore = from_key
        ignore = to_key
        # pull the latest changes of the snippets repository.
        with use_cases.OSInterface(self.snippets_repository) as osi:
            osi.execute_command("git pull")

        # read the snippet content from the snippet destination.
        snippet_content = File(
            self.snippets_repository, *snippet_source_dir.split(",")
        ).read_as_utf8()

        # copy the snippet content to the clipboard if no destination is provided.
        if snippet_destination_dir == "clipboard":
            pyperclip.copy(snippet_content)
        else:
            File(*snippet_destination_dir.split(",")).write_as_utf8(snippet_content)

    def get_folder(
        self,
        from_key: str,
        snippet_source_dir: str,
        to_key: str,
        snippet_destination_dir: str,
    ):
        """
        Retrieve a folder of snippets from the snippets repository.

        Parameters
        ----------
        from_key : str
            Placeholder for the "from" keyword.
        snippet_source_dir : str
            Comma-separated path inside the snippets repository.
        to_key : str
            Placeholder for the "to" keyword.
        snippet_destination_dir : str
            Comma-separated path to the local destination folder.

        Examples
        --------
        dev get snippet folder from snippet_repo_dir,subdir to path,to,local,folder
        """
        ignore = from_key
        ignore = to_key

        if snippet_source_dir == "clipboard" or snippet_destination_dir == "clipboard":
            raise ValueError("clipboard is not supported for folder snippets.")

        with use_cases.OSInterface(self.snippets_repository) as osi:
            osi.execute_command("git pull")

        source_dir = os.path.join(
            self.snippets_repository, *snippet_source_dir.split(",")
        )
        destination_dir = os.path.join(*snippet_destination_dir.split(","))

        self.__copy_directory(source_dir, destination_dir)

    def delete(
        self,
        snippet_destination_dir: str,
    ):
        """Example usage:

        dev delete snippet snippet_repo_dir,subdir,snippet_id
        """
        # delete the snippet file.
        File(self.snippets_repository, *snippet_destination_dir.split(",")).delete()

        snippet_id = snippet_destination_dir.split(",")[-1]

        # commit the changes to the git repository.
        self.__push_commit(f"feat: deleted {snippet_id} from {snippet_destination_dir}")

    def show_snippets(self, path: str | None = None):
        if path is None:
            print(self.snippets_repository)
            print(os.listdir(self.snippets_repository))
        else:
            print(os.path.join(self.snippets_repository, *path.split(",")))
            print(os.listdir(os.path.join(self.snippets_repository, *path.split(","))))
