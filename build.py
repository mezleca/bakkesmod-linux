#!/usr/bin/env python3

import os
import sys
import shutil
import subprocess
import platform
import argparse
from pathlib import Path

# paths
CWD = Path.cwd()
BUILD_DIR = CWD / "build"
EXTERNAL_DIR = CWD / "external"
SOURCE_DIR = CWD
BINARY_NAME = "simple_injector"

SYSTEM = platform.system()

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

def is_process_active(name: str, check: bool = False) -> bool:
    print(f"check process: {name}")

    result = subprocess.run(
        ["pgrep", "-f", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    active = result.returncode == 0

    if check and not active:
        print(f"process not running: {name}")
        sys.exit(1)

    return active

def tool_exists(tool: str):
    if shutil.which(tool) is None:
        raise Exception(f"{tool} not found in PATH")

def init() -> int:
    print("initializing submodules...")

    if Path("./.gitmodules").exists() and run("git submodule update --init --recursive", check=False)[0] != 0:
        print("failed to initialize submodules")
        return 1

    tool_exists("cmake")
    tool_exists("ninja")
    tool_exists("clang")

    return 0

def clean() -> int:
    if not BUILD_DIR.exists():
        print("build directory doesnt exist")
        return 0

    print("removing build directory...")
    try:
        shutil.rmtree(BUILD_DIR)
        print("build directory removed")
        return 0
    except PermissionError:
        print("permission denied - try running as admin/sudo")
        return 1

def get_cpu_count() -> int:
    if SYSTEM == "Linux":
        result = subprocess.run("nproc", shell=True, capture_output=True, text=True)
        cores = result.stdout.strip()
        return int(cores) if cores.isdigit() else os.cpu_count() or 4

    return os.cpu_count() or 4

def configure_linux(debug: bool) -> int:
    cache = BUILD_DIR / "CMakeCache.txt"

    if cache.exists():
        cache.unlink()

    BUILD_DIR.mkdir(exist_ok=True)

    cmd = (
        f"cmake -G Ninja "
        f"-B {BUILD_DIR} "
        f"-S {SOURCE_DIR} "
        f"-DCMAKE_BUILD_TYPE=Release "
        f"-DOUTPUT_NAME={BINARY_NAME}"
    )

    return run(cmd)[0]

def configure_windows(debug: bool) -> int:
    cache = BUILD_DIR / "CMakeCache.txt"

    if cache.exists():
        cache.unlink()

    BUILD_DIR.mkdir(exist_ok=True)

    cmd = (
        f"cmake -G Ninja "
        f"-B {BUILD_DIR} "
        f"-S {SOURCE_DIR} "
        f"-DCMAKE_BUILD_TYPE=Release "
        f"-DOUTPUT_NAME={BINARY_NAME}"
    )

    return run(cmd)[0]

def configure(debug: bool) -> int:
    if SYSTEM == "Linux":
        return configure_linux(debug)
    elif SYSTEM == "Windows":
        return configure_windows(debug)
    else:
        print(f"unsupported platform: {SYSTEM}")
        return 1

def build(debug: bool) -> int:
    if not BUILD_DIR.exists():
        print("build directory doesnt exist, configuring...")
        if configure(debug) != 0:
            return 1

    cores = get_cpu_count()
    return run(f"ninja -C {BUILD_DIR} -j{cores}")[0]

def run_binary() -> int:
    candidates = [
        BUILD_DIR / BINARY_NAME,
        BUILD_DIR / f"{BINARY_NAME}.exe",
        BUILD_DIR / "Release" / f"{BINARY_NAME}.exe",
        BUILD_DIR / "Debug" / f"{BINARY_NAME}.exe",
    ]

    binary = next((path for path in candidates if path.exists()), None)

    if binary is None:
        print("binary not found in any expected location")
        print("build the project first")
        return 1

    if not binary.exists():
        print(f"binary not found at {binary}")
        print("build the project first")
        return 1

    return run(f"WINEFSYNC=1 WINE_PREFIX=\"/home/rel/Games/Heroic/Prefixes/default/Rocket League/pfx\" wine {str(binary)}")[0]

def main():
    parser = argparse.ArgumentParser(
        description="build script for c++ projects",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    _ = parser.add_argument(
        "command",
        choices=["init", "configure", "build", "clean", "run"],
        help="command to execute"
    )

    _ = parser.add_argument(
        "--debug",
        action="store_true",
        help="use debug build type"
    )

    _ = parser.add_argument(
        "--run",
        action="store_true",
        help="run binary after building"
    )

    args = parser.parse_args()

    commands = {
        "init": init,
        "configure": lambda: configure(args.debug),
        "build": lambda: build(args.debug),
        "clean": clean,
        "run": run_binary
    }

    exit_code = commands[args.command]()

    if args.command == "build" and exit_code == 0 and args.run:
        exit_code = run_binary()

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
