import platform
import shutil
import subprocess


def read_current_profile() -> dict[str, str | None]:
    if platform.system() != "Linux":
        return {"name": None, "source": "unsupported-platform", "status": "unavailable"}
    command_path = shutil.which("powerprofilesctl")
    if command_path is None:
        return {"name": None, "source": "powerprofilesctl", "status": "unavailable"}
    try:
        result = subprocess.run(
            [command_path, "get"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "name": None,
            "source": "powerprofilesctl",
            "status": f"error: {type(error).__name__}",
        }
    if result.returncode != 0:
        return {"name": None, "source": "powerprofilesctl", "status": "unavailable"}
    profile_name = result.stdout.strip()
    return {
        "name": profile_name or None,
        "source": "powerprofilesctl",
        "status": "available" if profile_name else "unavailable",
    }