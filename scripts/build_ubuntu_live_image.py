import argparse
import os
import platform
import shutil
import stat
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
IMAGE_CONFIG_SOURCE = REPOSITORY_ROOT / "packaging" / "ubuntu-live" / "config"
EXCLUDED_SOURCE_ITEMS = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "packaging",
    "scripts",
    "tests",
    "typings",
}


def _ignore_project_items(_: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in EXCLUDED_SOURCE_ITEMS or name.endswith((".pyc", ".pyo"))
    }


def prepare_build_tree(repository_root: Path, build_directory: Path) -> Path:
    repository_root = repository_root.resolve()
    build_directory = build_directory.resolve()
    config_directory = build_directory / "config"
    config_directory.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        repository_root / "packaging" / "ubuntu-live" / "config",
        config_directory,
        dirs_exist_ok=True,
    )

    application_directory = config_directory / "includes.chroot" / "opt" / "battery-os"
    application_directory.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        repository_root,
        application_directory,
        dirs_exist_ok=True,
        ignore=_ignore_project_items,
    )

    for executable in (
        config_directory / "hooks" / "live" / "0100-battery-os.hook.chroot",
        config_directory / "includes.chroot" / "usr" / "local" / "bin" / "battery-os",
    ):
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return build_directory


def build_image(
    repository_root: Path = REPOSITORY_ROOT,
    build_directory: Path | None = None,
    *,
    system_name: str | None = None,
    effective_uid: int | None = None,
    runner=None,
) -> Path:
    if (system_name or platform.system()) != "Linux":
        raise RuntimeError("Build the Ubuntu live image from Linux, not Windows or WSL without a working account.")

    current_uid = effective_uid
    if current_uid is None:
        get_effective_uid = getattr(os, "geteuid", None)
        current_uid = get_effective_uid() if get_effective_uid is not None else None
    if current_uid != 0:
        raise RuntimeError("Run the live-image build as root inside the Linux build environment.")

    live_build = shutil.which("lb")
    if live_build is None:
        raise RuntimeError("live-build is not installed. Install Ubuntu's live-build package first.")

    if build_directory is None:
        build_directory = repository_root / "build" / "ubuntu-live"
    build_directory = prepare_build_tree(repository_root, build_directory)

    run = runner or subprocess.run
    configuration = [
        live_build,
        "config",
        "--mode",
        "ubuntu",
        "--distribution",
        "noble",
        "--architectures",
        "amd64",
        "--binary-images",
        "iso-hybrid",
        "--debian-installer",
        "false",
        "--bootappend-live",
        "persistent",
        "--archive-areas",
        "main universe",
        "--apt-recommends",
        "true",
        "--iso-application",
        "Battery OS",
        "--iso-volume",
        "BATTERY_OS_NOBLE",
    ]
    run(configuration, cwd=build_directory, check=True)
    run([live_build, "build"], cwd=build_directory, check=True)
    return build_directory


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a bootable Ubuntu Battery OS live ISO.")
    parser.add_argument(
        "--build-directory",
        type=Path,
        default=REPOSITORY_ROOT / "build" / "ubuntu-live",
        help="Build directory (default: build/ubuntu-live)",
    )
    arguments = parser.parse_args()
    build_directory = build_image(build_directory=arguments.build_directory)
    images = sorted(build_directory.glob("*.iso"))
    if not images:
        raise RuntimeError(f"Build completed but no ISO was found in {build_directory}.")
    for image in images:
        print(f"Bootable live image: {image}")


if __name__ == "__main__":
    main()