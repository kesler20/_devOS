"""
The file api provides a better interface for editing files in python
"""

import typing as types
import json
import os
from pathlib import Path
import PyPDF2


class File:
    """
    A class for reading, writing and grabbing files.

    Parameters
    ----------
    filename : Path
        The path to the file to be manipulated.
    relative_path : Tuple[str]
        string arguments which correspond to the relative path of a file
        if the length of this tuple is none zero, the first argument will also be used to make
        a path using `os.path.join(filename, *relative_path)`

    Example
    -------
    ```python
    >>> lines = File("path/to/python/file").readlines()
    >>> lines = File("path", "to", "python","file").readlines()
    ```

    """

    def __init__(self, filename: types.Union[Path, str], *relative_path) -> None:
        if type(filename) == str:
            filename = Path(filename)

        if len(relative_path) > 0:
            filename = Path(os.path.join(filename, *relative_path))

        self.filename = filename.as_posix()  # type: ignore

        # Create parent directories if they don't exist
        dir_name = os.path.dirname(self.filename)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    def __repr__(self) -> str:
        return f"""
File(
    file_path={self.filename},
    filename={os.path.basename(self.filename)},
    exists={self.exists()}
)
        """

    def size(self) -> int:
        """Return the size of the file in bytes."""
        return os.path.getsize(self.filename)

    def exists(self) -> bool:
        """Returns True if the filename path passed to the constructor exists."""
        return os.path.exists(self.filename)

    def is_file(self) -> bool:
        """Returns True if the current path is a file."""
        return os.path.isfile(self.filename)

    def read(self) -> str:
        """
        Read the contents of the file.

        Returns
        -------
        str
            The contents of the file as a string.
        """
        with open(self.filename, "r") as file:
            content = file.read()
        return content

    def read_as_utf8(self) -> str:
        """
        Read the contents of the file with UTF-8 encoding.

        Returns
        -------
        str
            The contents of the file as a string.
        """
        with open(self.filename, "r", encoding="utf-8") as file:
            content = file.read()
        return content

    def append(self, content: str) -> None:
        """
        Append content to the file.

        Parameters
        ----------
        content : str
            The content to be appended to the file.
        """
        with open(self.filename, "a") as file:
            file.write(content + "\n")

    def append_as_utf8(self, content: str) -> None:
        """
        Append content to the file with UTF-8 encoding.

        Parameters
        ----------
        content : str
            The content to be appended to the file.
        """
        with open(self.filename, "a", encoding="utf-8") as file:
            file.write(content + "\n")

    def append_after_line(self, line_number: int, new_content: str) -> None:
        """
        Append new_content after a specific line in the file.

        Parameters
        ----------
        line_number : int
            The line number after which the new_content will be appended.
        new_content : str
            The new_content to be appended to the file.
        """
        with open(self.filename, "r") as file:
            existing_content: types.List[str] = file.readlines()
            existing_content.insert(line_number + 1, new_content)

        with open(self.filename, "w") as file:
            file.writelines(new_content)

    def append_after_example(self, example: str, new_content: str) -> None:
        """
        Append new_content after a line in the file that matches a specific example.

        Parameters
        ----------
        example : str
            A string that is present in the line after which the new_content will be appended.
        new_content : str
            The new_content to be appended to the file.
        """
        with open(self.filename, "r") as file:
            existing_content = file.readlines()

        for i, line in enumerate(existing_content):
            if example in line:
                existing_content.insert(i + 1, new_content)

        with open(self.filename, "w") as file:
            file.writelines(existing_content)

    def append_after_example_utf8(self, example: str, new_content: str) -> None:
        """
        Append new_content after a line in the file that matches a specific example.

        Parameters
        ----------
        example : str
            A string that is present in the line after which the new_content will be appended.
        new_content : str
            The new_content to be appended to the file.
        """
        with open(self.filename, "r", encoding="utf-8") as file:
            existing_content = file.readlines()

        for i, line in enumerate(existing_content):
            if example in line:
                existing_content.insert(i + 1, new_content)

        with open(self.filename, "w", encoding="utf-8") as file:
            file.writelines(existing_content)

    def write_as_utf8(self, content: str) -> None:
        """
        Write content to the file with UTF-8 encoding, overwriting the existing content.

        Parameters
        ----------
        content : str
            The content to be written to the file.
        """
        with open(self.filename, "w", encoding="utf-8") as file:
            file.write(content)

    def write(self, content: str) -> None:
        """
        Write content to the file, overwriting the existing content.

        Parameters
        ----------
        content : str
            The content to be written to the file.
        """
        with open(self.filename, "w") as file:
            file.write(content)

    def readlines_as_utf8(self) -> types.List[str]:
        """
        Read the lines of the file with UTF-8 encoding.

        Returns
        -------
        list[str]
            The lines of the file as a list of strings.
        """
        with open(self.filename, "r", encoding="utf-8") as file:
            content: types.List[str] = file.readlines()
        return content

    def update_line(self, line_number: int, new_content: str) -> None:
        """
        Update a specific line in the file.

        Parameters
        ----------
        line_number : int
            The line number to be updated.
        new_content : str
            The new content to be written to the specified line.
        """
        with open(self.filename, "r") as file:
            content = file.readlines()

        content[line_number] = new_content

        with open(self.filename, "w") as file:
            file.writelines(content)

    def update_line_by_example(self, example: str, new_content: str) -> None:
        """
        Update a line in the file that matches a specific example.

        Parameters
        ----------
        example : str
            A string that is present in the line to be updated.
        new_content : str
            The new content to be written to the specified line.
        """
        with open(self.filename, "r") as file:
            content = file.readlines()

        for i, line in enumerate(content):
            if example in line:
                content[i] = new_content

        with open(self.filename, "w") as file:
            file.writelines(content)

    def readlines(self) -> types.List[str]:
        """
        Read the lines of the file.

        Returns
        -------
        list[str]
            The lines of the file as a list of strings.
        """
        with open(self.filename, "r") as file:
            content = file.readlines()
        return content

    def get_json(self) -> types.Dict[types.Any, types.Any]:
        """
        Read the contents of a JSON file.

        Returns
        -------
        dict
            The contents of the JSON file as a dictionary.
        """
        with open(self.filename, "r") as json_file:
            content: types.Dict[types.Any, types.Any] = json.loads(json_file.read())
        return content

    def read_text_from_pdf(self) -> str:
        """Read the contents of a PDF file.

        Returns
        -------
        All the text of all the pages of the PDF file.
        """
        if not self.filename.lower().endswith("pdf"):
            raise ValueError("File is not a PDF: " + self.filename)

        text = ""
        try:
            with open(self.filename, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text() if page.extract_text() else ""
                    text += page_text + " "
        except Exception as e:
            # Handle specific exceptions as needed, and consider logging or re-raising them
            print(f"Error processing file {self.filename}: {e}")
            return ""

        return text.strip()

    def write_json(
        self, content: types.Union[types.Dict[str, types.Any], types.List[types.Any]]
    ) -> None:
        """
        Write the contents to a JSON file.

        Parameters
        ----------
        content : dict or list
            The content to be written to the JSON file.
        """
        with open(self.filename, "w") as json_file:
            json_file.write(json.dumps(content, indent=2))

    def writeline(self, content: str) -> None:
        """
        Write a single line to the file, overwriting the existing content.

        Parameters
        ----------
        content : str
            The content to be written as a single line to the file.
        """
        with open(self.filename, "w") as file:
            file.write(f"{content}\n")

    def writeline_as_utf8(self, content: str) -> None:
        """
        Write a single line to the file with UTF-8 encoding, overwriting the existing content.

        Parameters
        ----------
        content : str
            The content to be written as a single line to the file.
        """
        with open(self.filename, "w", encoding="utf-8") as file:
            file.write(f"{content}\n")

    def writelines(self, content: types.List[str]) -> None:
        """
        Write multiple lines to the file, overwriting the existing content.

        Parameters
        ----------
        content : list[str]
            A list of strings to be written as lines to the file.
        """
        with open(self.filename, "w") as file:
            file.writelines([f"{line}" for line in content])

    def writelines_as_utf8(self, content: types.List[str]) -> None:
        """
        Write multiple lines to the file with UTF-8 encoding, overwriting the existing content.

        Parameters
        ----------
        content : list[str]
            A list of strings to be written as lines to the file.
        """
        with open(self.filename, "w", encoding="utf-8") as file:
            file.writelines([f"{line}" for line in content])

    def read_line_by_condition(
        self, condition: types.Callable[[str], bool]
    ) -> types.List[str]:
        """
        Read lines from the file that meet a specific condition.

        Parameters
        ----------
        condition : Callable
            A function that takes a line as input and returns a boolean value.
            If True, the line will be included in the output list.

        Returns
        -------
        list[str]
            A list of lines from the file that meet the specified condition.
        """
        with open(self.filename, "r") as file:
            content: types.List[str] = file.readlines()

        return list(filter(condition, content))

    def rename_file(self, new_name: str) -> None:
        """
        Rename the file.

        Parameters
        ----------
        new_name : str
            The new name of the file.
        """
        os.rename(self.filename, os.path.join(os.path.dirname(self.filename), new_name))

    def delete(self) -> None:
        """
        Delete the file.

        Returns
        -------
        None
        """
        os.remove(self.filename)
