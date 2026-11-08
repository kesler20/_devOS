import argparse
import os
import pathlib
import shutil
import subprocess
import sys


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dev ui")
    parser.add_argument(
        "frontend",
        nargs="?",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parents[2] / "frontend",
    )
    parser.add_argument("--port", type=int, default=3000)
    options = parser.parse_args(arguments)
    if not 1 <= options.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    node = shutil.which("node")
    entrypoint = options.frontend / "node_modules/react-scripts/scripts/start.js"
    if node is None or not entrypoint.is_file():
        print(
            "Install Node.js and run pnpm install in the selected devOS frontend directory",
            file=sys.stderr,
        )
        return 1
    environment = dict(os.environ, HOST="127.0.0.1", PORT=str(options.port))
    result = subprocess.run(
        [node, str(entrypoint.resolve())],
        cwd=options.frontend,
        env=environment,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
