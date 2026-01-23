import subprocess
import sys
import os
import shutil

from pathlib import Path

def copy_tree(src: Path, dst: Path, symlink_dirs: list[str] | None = None):
    symlink_dirs = symlink_dirs or []

    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        target_dir = dst / rel

        # check if current dir should be symlinked
        if str(rel) in symlink_dirs:
            # remove existing dir/symlink if any
            if target_dir.exists() or target_dir.is_symlink():
                if target_dir.is_symlink():
                    target_dir.unlink()
                else:
                    shutil.rmtree(target_dir)

            target_dir.symlink_to(Path(root), target_is_directory=True)
            dirs.clear()  # dont descend into symlinked dirs
            continue

        target_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            src_file = Path(root) / file
            dst_file = target_dir / file
            shutil.copy2(src_file, dst_file)

def get_resource_folder():
    return Path(__file__).parent.parent / "resources"

def get_resource_path(filename):
    return get_resource_folder() / filename

def get_file_content(location: str) -> str:
    content = ""

    try:
        with open(location, "r", encoding="utf-8") as file:
            content = file.read()
    except FileNotFoundError:
        print("file was not found.")
    except Exception as e:
        print(f"an error occurred: {e}")

    return content

def run(
    cmd: str,
    check: bool = True,
    env: dict[str, str] | None = None,
    capture: bool = False,
    wait: bool = True,
) -> tuple[int, str]:
    print(f"exec: {cmd}")

    if wait:
        result = subprocess.run(
            cmd,
            shell=True,
            env=env,
            capture_output=capture,
            text=capture,
        )

        if check and result.returncode != 0:
            print(f"command failed with exit code {result.returncode}")
            sys.exit(result.returncode)

        return result.returncode, result.stdout

    _ = subprocess.Popen(
        cmd,
        shell=True,
        env=env,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=capture,
    )

    return 0, ""

def get_process_env(process_name) -> tuple[int, dict[str, str]] | None:
    try:
        # get all pids matching the process
        result = subprocess.run(
            ["pgrep", "-f", process_name],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            return None

        if result.returncode != 0:
            return None

        pids = result.stdout.strip().split("\n")

        # we dont any wrapper process
        wrappers = ["umu-run", "proton", "pv-adverb", "steam-runtime"]

        for pid in pids:
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmdline = f.read().decode("utf-8", errors="ignore")

                # skip if its a wrapper process
                if any(wrapper in cmdline for wrapper in wrappers):
                    continue

                # this is the real process, grab its env
                with open(f"/proc/{pid}/environ", "rb") as f:
                    environ_data = f.read().decode("utf-8", errors="ignore")

                env_dict: dict[str, str] = {}

                for entry in environ_data.split("\0"):
                    if "=" in entry:
                        key, value = entry.split("=", 1)
                        env_dict[key] = value

                return int(pid), env_dict

            except (FileNotFoundError, PermissionError):
                continue

        return None

    except (FileNotFoundError, PermissionError):
        return None
