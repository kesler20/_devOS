from __future__ import annotations

from pathlib import Path
from typing import Any
import json


class FileObjectStorageAdapter:
    """Store JSON-compatible objects under a local folder.

    Parameters
    ----------
    root_directory
        Root folder used as object storage.
    """

    def __init__(self, root_directory: str | Path) -> None:
        self.__root_directory = Path(root_directory)
        self.__root_directory.mkdir(parents=True, exist_ok=True)

    def __resolve_path(self, resource_locator: str) -> Path:
        object_path = (self.__root_directory / resource_locator).resolve()
        root_path = self.__root_directory.resolve()
        if root_path not in [object_path, *object_path.parents]:
            raise ValueError("resource_locator must stay inside root_directory.")
        return object_path

    def write_object(self, resource_locator: str, content: Any) -> bool:
        """Write an object to a local file.

        Parameters
        ----------
        resource_locator
            Relative object path.
        content
            JSON-compatible content.

        Returns
        -------
        bool
            ``True`` when the write succeeds.
        """

        if not resource_locator or content is None:
            return False
        object_path = self.__resolve_path(resource_locator)
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_text(json.dumps(content), encoding="utf-8")
        return True

    def read_object(self, resource_locator: str) -> Any | None:
        """Read an object from a local file.

        Parameters
        ----------
        resource_locator
            Relative object path.

        Returns
        -------
        Any | None
            Decoded content, or ``None`` when missing.
        """

        if not resource_locator:
            return None
        object_path = self.__resolve_path(resource_locator)
        if not object_path.exists():
            return None
        return json.loads(object_path.read_text(encoding="utf-8"))

    def delete_object(self, resource_locator: str) -> bool:
        """Delete a local object.

        Parameters
        ----------
        resource_locator
            Relative object path.

        Returns
        -------
        bool
            ``True`` when the object existed and was deleted.
        """

        if not resource_locator:
            return False
        object_path = self.__resolve_path(resource_locator)
        if not object_path.exists():
            return False
        object_path.unlink()
        return True
