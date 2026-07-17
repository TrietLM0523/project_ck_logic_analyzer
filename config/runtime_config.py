# config/runtime_config.py

import os
import shutil
from pathlib import Path


SIGROK_CLI_ENV = "LOGIC_ANALYZER_SIGROK_CLI"


def resolve_sigrok_cli_path() -> str:
    """
    Resolve sigrok-cli without hard-coding one developer's absolute path.

    Search order:
    1. LOGIC_ANALYZER_SIGROK_CLI environment variable
    2. sigrok-cli available in PATH
    3. Project-local / sibling Windows folders commonly used by this repo
    """

    environment_path = os.environ.get(SIGROK_CLI_ENV)

    if environment_path:
        candidate = Path(environment_path).expanduser()

        if candidate.is_file():
            return str(candidate.resolve())

        raise FileNotFoundError(
            f"Environment variable {SIGROK_CLI_ENV} points to a missing file: "
            f"{candidate}"
        )

    discovered_path = shutil.which("sigrok-cli")

    if discovered_path:
        return discovered_path

    project_root = Path(__file__).resolve().parents[1]

    candidates = [
        project_root / "tools" / "sigrok-cli" / "sigrok-cli.exe",
        project_root / "sigrok_cli" / "sigrok-cli" / "sigrok-cli.exe",
        project_root.parent / "sigrok_cli" / "sigrok-cli" / "sigrok-cli.exe",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())

    searched_locations = "\n".join(
        f"- {candidate}" for candidate in candidates
    )

    raise FileNotFoundError(
        "sigrok-cli.exe was not found.\n\n"
        "Either add sigrok-cli to PATH, place it in a project-local tools folder, "
        f"or set {SIGROK_CLI_ENV}.\n\n"
        "Searched locations:\n"
        f"{searched_locations}"
    )
