from __future__ import annotations

import os
import sys
import time
import typing
import colorama


class OperatingSystemAdapter:
    """Provide scoped OS operations with logging.

    Attributes
    ----------
    directory : str
        Target directory to execute commands in.
    previous_directory : str
        Working directory before entering the context manager.
    """

    def __init__(self, directory: str):
        """Initialize the interface with a target directory.

        Parameters
        ----------
        directory : str
            Directory to switch into when used as a context manager.
        """
        self.__directory = directory
        self.__previous_directory = os.getcwd()

    def __enter__(self) -> OperatingSystemAdapter:
        self.__previous_directory = os.getcwd()
        self.log_message(f"changing directory to {self.__directory}")
        os.chdir(self.__directory)
        return self

    def __exit__(self, *args) -> None:
        self.log_message(f"changing directory to {self.__previous_directory}")
        os.chdir(self.__previous_directory)

    def log_message(
        self, message: str, error: bool = False, is_command: bool = False
    ) -> None:
        """Print a formatted message to the console.

        Parameters
        ----------
        message : str
            the message to print
        error : bool, optional
            whether the message is an error message, by default False
        is_command : bool, optional
            whether the message is a command, by default False

        Notes
        -----
        If the message is empty i.e. `log_message("")`,
        the method will print a new line and wait for 1 second.
        """
        if message == "":
            time.sleep(1)
            print("\n")
        emoji = "🙀" if error else "😼"
        if is_command is False:
            msg = f"{emoji} ------------- {message}"
        else:
            msg = f"\n{emoji} | {self.__directory} - {message} \n"

        if error:
            self.__print_message(f"{colorama.Fore.RED}{msg}{colorama.Style.RESET_ALL}")
        else:
            self.__print_message(msg)

    def __print_message(self, message: str) -> None:
        try:
            print(message)
        except UnicodeEncodeError:
            stdout_encoding = sys.stdout.encoding or "utf-8"
            safe_message = message.encode(
                stdout_encoding,
                errors="replace",
            ).decode(stdout_encoding)
            print(safe_message)

    def execute_command(self, command: str, error: bool = False) -> None:
        """Execute a command using `os.system`.

        Parameters
        ----------
        command : str
            The command to execute.
        error : bool, optional
            Whether to log the command as an error, by default False.

        Notes
        -----
        For echo commands, pass arguments directly to the shell to avoid
        quoting pitfalls.

        Examples
        --------
        >>> execute_command("python --version")
        """

        if error:
            self.log_message(command, error=True, is_command=True)

        self.log_message(command, error=error, is_command=True)
        result = os.system(command)
        if result:
            raise RuntimeError(f"Command failed with exit status {result}")

    @staticmethod
    def get_home_path() -> str:
        """Return the user home directory path.

        Returns
        -------
        str
            Home directory path.
        """
        return os.path.expanduser("~")

    @staticmethod
    def join(*paths: str) -> str:
        """Join multiple path components into a single path.

        Parameters
        ----------
        *paths : str
            Path components to join.

        Returns
        -------
        str
            Joined path.
        """
        if len(paths) == 0:
            raise ValueError("At least one path component must be provided.")
        elif len(paths) == 1:
            return paths[0]
        else:
            return os.path.join(*paths)

    def prompt(
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

    def prompt_optional(
        self, label: str, default: typing.Optional[str] = None
    ) -> typing.Optional[str]:
        suffix = f" [{default}]" if default not in (None, "") else ""
        raw = input(f"{label}{suffix} (leave blank to skip): ").strip()
        if raw:
            return raw
        return default if default else None
