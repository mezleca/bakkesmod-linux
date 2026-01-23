import requests
import zipfile

from pathlib import Path
from PySide6 import os
from constants import (
    BAKKESMOD_GITHUB_LATEST,
    BAKKESMOD_LOCATION,
    BAKKESMOD_UPDATER_URL,
    PREFIX_REL_LOCATION
)
from utils import copy_tree, get_file_content, get_process_env, get_resource_folder, run

SYMLINK_DIRS = ["cfg", "plugins"]

class BakkesHelper:
    def __init__(self):
        self.injected = False
        self.wine_prefix = None
        self.rl_process = None
        self.loader = None
        self.cache_updated = False

    def install(self, progress):
        progress.status("downloading latest bakkesmod version...")

        temp_location = "/tmp/bakkesmod.zip"
        res = requests.get(BAKKESMOD_GITHUB_LATEST, stream=True)

        total_size = int(res.headers.get("content-length", 0))
        downloaded = 0

        with open(temp_location, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                downloaded += len(chunk)
                f.write(chunk)

                if total_size > 0:
                    percentage = int((downloaded / total_size) * 100)
                    progress.progress("downloading...", percentage)

        progress.status("extracting files...")

        BAKKESMOD_LOCATION.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(temp_location, "r") as zip_ref:
            zip_ref.extractall(BAKKESMOD_LOCATION)

        progress.status("cleaning up...")
        self.cache_updated = True
        os.remove(temp_location)

    def update(self, progress):
        # install if we dont have installed yet
        if not BAKKESMOD_LOCATION.exists():
            print("updater: bakkesmod cache not found, installing")
            self.install(progress)
            return

        current_version = self.get_current_version(BAKKESMOD_LOCATION)

        if current_version is None:
            print("updater: invalid cache version, reinstalling")
            self.install(progress)
            return

        progress.status("checking for updates...")

        if not self.check_version_mismatch(current_version):
            progress.done("already on latest version")
            return

        self.install(progress)

    def get_current_version(self, location: Path) -> int | None:
        version_path = location / "version.txt"
        version_str = get_file_content(str(version_path))

        if version_str == "":
            return None

        try:
            return int(version_str)
        except ValueError:
            return None

    def get_bakkesmod_updater_data(self, version: int) -> str | None:
        res = requests.get(f"{BAKKESMOD_UPDATER_URL}/{version}")

        if res.status_code != 200:
            return None

        data = res.json()
        return data.get("update_info") or None

    def check_version_mismatch(self, current_version: int) -> bool:
        print(f"checking version: {current_version}")
        data = self.get_bakkesmod_updater_data(current_version)
        return data is not None

    def resolve_wine_loader(self, loader_path: str) -> str:
        if loader_path.startswith("/run/host/"):
            return loader_path.replace("/run/host/", "/", 1)
        return loader_path

    def get_prefix_bakkesmod_path(self) -> Path:
        if self.wine_prefix is None:
            raise RuntimeError("wine_prefix not initialized")

        return Path(self.wine_prefix) / PREFIX_REL_LOCATION

    def ensure_prefix_files(self, progress) -> bool:
        prefix_path = self.get_prefix_bakkesmod_path()
        cache_version = self.get_current_version(BAKKESMOD_LOCATION)

        if cache_version is None:
            progress.error("invalid cached bakkesmod version")
            return False

        if not prefix_path.exists():
            progress.status("installing bakkesmod into prefix...")
            copy_tree(BAKKESMOD_LOCATION, prefix_path, SYMLINK_DIRS)
            return True

        prefix_version = self.get_current_version(prefix_path)

        if prefix_version is None:
            progress.error("invalid bakkesmod version in prefix, please reinstall")
            return False

        if prefix_version != cache_version:
            print("bakkesmod version mismatch", prefix_version, cache_version)

            # wait until the user manually updates (just click the button bruh)
            if not self.cache_updated:
                progress.error("bakkesmod version mismatch, please run update")
                return False

            # user updated so lets update the prefix files
            progress.status("syncing updated bakkesmod into prefix...")
            copy_tree(BAKKESMOD_LOCATION, prefix_path, SYMLINK_DIRS)
            return True

        return True

    def inject(self, progress):
        if self.injected:
            progress.done("already injected")
            return

        progress.progress("resolving rocket league process...", 5)
        result = get_process_env("RocketLeague.exe")

        if result is None:
            progress.error("rocket league process not found")
            return

        pid, env = result

        self.rl_process = pid
        self.wine_prefix = env["WINEPREFIX"]
        self.loader = self.resolve_wine_loader(env["WINELOADER"])

        if self.wine_prefix is None:
            progress.error("failed to resolve wine prefix")
            return

        if not Path(self.loader).exists():
            progress.error(f"wine loader not found: {self.loader}")
            return

        progress.progress("copying bakkesmod files...", 20)

        # ensure bakkesmod files inside prefix
        if not self.ensure_prefix_files(progress):
            return

        injector_path = get_resource_folder() / "simple_injector.exe"

        if not injector_path.exists():
            progress.error("missing simple_injector.exe... please reinstall")
            return

        progress.progress("injecting...", 50)

        code, _ = run(
            cmd=f'WINEPREFIX="{self.wine_prefix}" {self.loader} {injector_path}',
            capture=True,
            wait=True,
            check=False
        )

        # EXIT_OK = 0,
        # ERR_DLL_NOT_FOUND = 1,
        # ERR_PROCESS_NOT_FOUND = 2,
        # ERR_INJECT_FAILED = 3,
        if code == 0:
            progress.done("injected")
            self.injected = True
            self.cache_updated = False
        elif code == 1:
            progress.error("failed to inject (dll not found)")
        elif code == 2:
            progress.error("failed to inject (process not found)")
        else:
            progress.error("failed to inject (unknown)")
