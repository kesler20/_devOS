import subprocess
import sys
import os


def main(home_path_to_devos: str):
    """Run the FastAPI server and the frontend development server.

    Parameters
    ----------
    home_path_to_devos : str
        The path segments from the user's home directory to the devOS project.
        (comma-separated string) E.g., "projects,devOS"

    Examples
    --------
    dev ui protocol,devOS
    """
    subprocess.Popen(
        [
            sys.executable,  # Path to the current Python interpreter
            "-m",
            "uvicorn",
            "devOS.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        shell=True,
    )
    os.system(
        f"cd {os.path.join(os.path.expanduser('~'), *home_path_to_devos.split(','), 'frontend')} && npm start"
    )


if __name__ == "__main__":
    main("protocol,devOS")
