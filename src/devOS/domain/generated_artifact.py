import dataclasses
import pathlib


@dataclasses.dataclass(frozen=True)
class GeneratedArtifact:
    path: pathlib.Path
    content: str
    marker: str

    def validate_destination(self, sources: list[pathlib.Path]) -> None:
        if self.path.resolve() in {source.resolve() for source in sources}:
            raise ValueError("Generated output must not replace a source file")
        for parent in self.path.parents:
            if parent.exists() and not parent.is_dir():
                raise ValueError(f"Output parent must be a directory: {parent}")
        if self.path.exists():
            if not self.path.is_file() or not self.path.read_text(
                encoding="utf-8"
            ).startswith(self.marker):
                raise ValueError(
                    f"Preserving project-owned file {self.path}. Choose a new generated output path"
                )
