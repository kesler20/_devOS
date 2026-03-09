from git import Repo
import enum
import typing
from random import randint
from devOS.use_cases import use_cases
import os

from devOS.use_cases.utils.file_io import File


class TypesOFRelease(enum.Enum):
    """Supported release types for tagging versions."""

    MAJOR = "major"
    MINOR = "minor"
    FIX = "fix"


TypeOfReleaseTypes = typing.Literal["major", "minor", "fix"]


class ManageGitRepositoryUseCase(use_cases.OSInterface):
    """Manage git repository releases and commit workflows.

    Attributes
    ----------
    current_repo : git.Repo
        Repository object for the current project.
    """

    def __init__(self) -> None:
        """Initialize repository manager for the current repo.

        Parameters
        ----------
        app_type : SupportedLanguages, optional
            Application type used to resolve version handling, by default
            SupportedLanguages.PYTHON.
        """
        super().__init__(os.getcwd())
        self.current_repo = Repo(".", search_parent_directories=True)

    def _fetch_remote_tags(self):
        """Fetch tags from remote to ensure local tags are up-to-date."""
        try:
            self.execute_command("git fetch --tags")
        except Exception as e:
            self.log_message(f"Failed to fetch remote tags: {e}", error=True)

    @property
    def latest_version(self):
        # Fetch remote tags first
        self._fetch_remote_tags()
        tags = sorted(self.current_repo.tags, key=lambda t: t.commit.committed_datetime)
        if tags:
            latest_tag = str(tags[-1])
        else:
            latest_tag = "v0.0.0"
        return latest_tag

    def __style_commit_message(self, commit_message: str) -> str:
        """style_commit_message styles the commit messages according to the
        Conventional Commits convention @see https://www.conventionalcommits.org/en/v1.0.0/
        - `fix`: A bug fix
        - `refactor`: A code refactor
        - `docs`: Documentation changes
        - `chore`: Changes to build process, dependencies, etc.
        - `style`: Changes to code style, formatting, etc.
        - `test`: Adding or updating tests
        - `perf`: Performance improvements

        Parameters
        ---
        commit_message : str
          the commit message should contain a marker such as the following
          - `-d ` -> docs
          - `-t ` -> tests
          - `-f ` -> feat (feature)
          - `-b ` -> fix (bug)
          - `-s ` -> style
          - `-r ` -> refactor
          - `-p ` -> perf
          - `-c -> chore
          - `-bc ` -> BREAKING CHANGE
          - `TODO:` -> TODO commit

        Returns
        ---
        str
          the new formatted commit message with an emoji i.e.
          - -d changed the README -> docs: changed the README 📰
        """
        print(commit_message)
        # this is to make commit messages more interesting
        code_commit_message_emojis = ["😕", "⭐", "✊", "🤝", "👐"]
        if commit_message.startswith("-t "):
            message_prefix = "test:"
            message_suffix = "🧪"
            commit_message = commit_message.replace("-t ", " ")

        elif commit_message.startswith("-d "):
            message_prefix = "docs:"
            message_suffix = "📰"
            commit_message = commit_message.replace("-d ", " ")

        elif commit_message.startswith("-f "):
            message_prefix = "feat:"
            message_suffix = code_commit_message_emojis[
                randint(0, len(code_commit_message_emojis) - 1)
            ]
            commit_message = commit_message.replace("-f ", " ")

        elif commit_message.startswith("-b "):
            message_prefix = "fix:"
            message_suffix = "⚙️"
            commit_message = commit_message.replace("-b ", " ")

        elif commit_message.startswith("-s "):
            message_prefix = "style:"
            message_suffix = "✨"
            commit_message = commit_message.replace("-s ", " ")

        elif commit_message.startswith("-r "):
            message_prefix = "refactor:"
            message_suffix = "🐍 💫"
            commit_message = commit_message.replace("-r ", " ")

        elif commit_message.startswith("-p "):
            message_prefix = "perf:"
            message_suffix = "💨"
            commit_message = commit_message.replace("-p ", " ")

        elif commit_message.startswith("-c "):
            message_prefix = "chore:"
            message_suffix = "🪴"
            commit_message = commit_message.replace("-c ", " ")

        elif commit_message.startswith("-bc "):
            message_prefix = "BREAKING CHANGE:"
            message_suffix = "😱"
            commit_message = commit_message.replace("-bc ", " ")

        elif commit_message.startswith("TODO:"):
            message_prefix = ""
            message_suffix = "🔴🔴🔴"

        else:
            message_prefix = ""
            message_suffix = ""

        commit_message = message_prefix + commit_message + message_suffix

        # process the scope of the message
        if commit_message.find("--") != -1:
            scope = commit_message.split("--")[1].split(" ")[0]
            commit_message = commit_message.replace(f": --{scope}", f"({scope}):")
            commit_message = commit_message.replace(f" --{scope}", f"({scope}):")
            commit_message = commit_message.replace(f"--{scope}", f"({scope}):")

        return commit_message

    def __increase_patch_version(self) -> str:
        major, minor, patch = map(int, self.latest_version[1:].split("."))
        patch += 1
        new_version = f"v{major}.{minor}.{patch}"
        self.execute_command(f"git tag {new_version}")
        return new_version

    def __increase_minor_change_version(self) -> str:
        major, minor, patch = map(int, self.latest_version[1:].split("."))
        minor += 1
        patch = 0  # Reset patch version after minor version increment
        new_version = f"v{major}.{minor}.{patch}"
        self.execute_command(f"git tag {new_version}")
        return new_version

    def __increase_major_change_version(self) -> str:
        major, minor, patch = map(int, self.latest_version[1:].split("."))
        major += 1
        minor = patch = (
            0  # Reset minor and patch versions after major version increment
        )
        new_version = f"v{major}.{minor}.{patch}"
        self.execute_command(f"git tag {new_version}")
        return new_version

    def create_release_tag(self, release_type: TypeOfReleaseTypes) -> str | None:
        """
        Create a new release tag given the type of release.

        Parameters
        ----------
        release_type : TypeOfReleaseTypes
            The type of release: "major", "minor", or "fix".

        Returns
        -------
        str or None
            The new version string if successful, otherwise None.
        """
        release_type_map = {
            TypesOFRelease.FIX.value: self.__increase_patch_version,
            TypesOFRelease.MINOR.value: self.__increase_minor_change_version,
            TypesOFRelease.MAJOR.value: self.__increase_major_change_version,
        }
        release_action = release_type_map.get(release_type)
        if release_action is None:
            self.log_message(
                f"Failed to release the latest changes ❌ for: {self.latest_version}",
                error=True,
            )
            self.log_message(
                "Select one of the following: major, minor, fix", error=True
            )
            return None

        # Update the version by creating a new tag
        new_version = release_action()
        self.log_message(f"Updating the version number to {new_version}")
        return new_version

    def display_current_version(self) -> None:
        """Print the latest version tag to stdout."""
        print(self.latest_version)

    def delete_tag(self, tag_name):
        """Delete a tag locally and on the remote.

        Parameters
        ----------
        tag_name : str
            Tag name to delete.
        """
        self.execute_command(f"git tag -d {tag_name}")
        self.execute_command(f"git push --delete origin {tag_name}")

    def add_commit_message(self, *args, push: bool = True) -> None:
        """Create and optionally push a commit with a styled message.

        Parameters
        ----------
        commit_message : str
            the commit message should contain a marker such as the following
            - -d -> docs
            - -t -> tests
            - -f -> feat (feature)
            - -b -> fix (bug)
            - -s -> style
            - -r -> refactor
            - -p -> perf
            - -c -> chore
            - -bc -> BREAKING CHANGE
            - TODO: -> TODO commit
        push : bool, optional
            whether to push the commit after creating it, by default True

        Examples
        --------
        devOS commit -f added new feature
        devOS commit -b fixed a bug
        devOS commit -d updated documentation

        If no commit message is provided, the method will show the git diff
        and prompt the user to enter a commit message.
        for instance

        devOS commit
        """
        self.execute_command("git pull")

        # build commit message
        if len(args) == 1:
            commit_message = args[0]
        elif len(args) == 0:
            # if no commit message is provided, show the git diff
            self.execute_command("git diff")
            raw_user_input = input("Enter your commit message: ").strip()

            # if no commit message is provided, use a default one.
            commit_message = (
                raw_user_input if raw_user_input != "" else "-c make it better"
            )
        else:
            commit_message = " ".join(args)

        # style the commit message
        styled_commit_message = self.__style_commit_message(commit_message)

        # add commit message and push
        self.execute_command("git add .")
        self.execute_command(f'git commit -m "{styled_commit_message}"')
        if push:
            self.execute_command("git push")
            print("\nnew commit pushed successfully ✨\n", styled_commit_message)

    def release_new_version(self, *args) -> None:
        """Release a new version and tag the repository.

        Examples
        --------
        devOS release major -f added new feature
        devOS release minor -b fixed a bug
        devOS release fix -d updated documentation

        if no commit message is provided, the method will prompt the user to enter a commit message.
        for instance:
        devOS release minor
        then the user will be prompted to enter a commit message.

        devOS release major
        """
        # if no release type is provided, show error message
        if len(args) != 1:
            self.log_message(
                "Select one of the following: major, minor, fix", error=True
            )
            return

        # the first item in the args is the release type
        release_type = args[0]

        # create the release tag depending on the release type
        new_version = self.create_release_tag(release_type)

        # if new version is created, push the commit message and the tag
        if new_version:

            # update uv and package.json files with the new version.
            self.execute_command(f"uv version {new_version.replace('v', '')}")
            if File("package.json").exists():
                self.execute_command(
                    f"npm version {new_version.replace('v', '')} --no-git-tag-version"
                )
            else:
                self.log_message("trying again in the frontend folder...")
                self.execute_command(
                    f"cd frontend && npm version {new_version.replace('v', '')} --no-git-tag-version && cd .."
                )

            # add commit message using the rest of the args
            commit_message = args[1:] if len(args) > 1 else ""
            self.add_commit_message(*commit_message, push=False)

            # add the new tag and push it to the remote repo
            self.execute_command(f"git push origin {new_version}")
            self.log_message(f"🎉 Successfully released new version: {new_version} 🚀")
        else:
            self.log_message("Failed to release new version", error=True)
