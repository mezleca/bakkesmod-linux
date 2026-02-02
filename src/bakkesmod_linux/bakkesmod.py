import os
import shutil
import zipfile
import requests

from pathlib import Path
from typing import Callable
from bakkesmod_linux.config import ConfigManager
from bakkesmod_linux.constants import (
    BAKKESMOD_LOCATION,
    PROTECTED_PATHS
)
from bakkesmod_linux.utils import (
    copy_tree,
    filter_game_env,
    get_file_content,
    get_process_env,
    run,
    win_path_to_linux
)

SYMLINK_DIRS = ["cfg", "plugins"]
WATCHER_INTERVAL_MS = 3000

class BakkesHelper:
    def __init__(self, config: ConfigManager | None = None):
        self.config = config or ConfigManager()
        self.injected = False
        self.wine_prefix: str | None = None
        self.rl_process = None
        self.loader: str | None = None
        self.cache_updated = False
        self.rl_running = False
        self.bakkesmod_path: Path | None = None
        self.game_env: dict | None = None
        self._on_process_change: Callable[[bool], None] | None = None

    def set_process_callback(self, callback: Callable[[bool], None]) -> None:
        self._on_process_change = callback

    def check_rl_process(self):
        result = get_process_env("RocketLeague.exe")
        was_running = self.rl_running
        self.rl_running = result is not None

        if self.rl_running and result:
            _, env = result
            self.wine_prefix = env["WINEPREFIX"]
            self.loader = self._resolve_wine_loader(env["WINELOADER"])
            self.game_env = filter_game_env(env)

            if not self.bakkesmod_path:
                self.resolve_install_path()

        # reset injection state when process dies
        if was_running and not self.rl_running:
            self.injected = False

        # notify ui about state change
        if self._on_process_change and was_running != self.rl_running:
            self._on_process_change(self.rl_running)

    def resolve_install_path(self, progress=None):
        if not self.wine_prefix or not self.loader:
            return False

        injector_path = BAKKESMOD_LOCATION / "simple_injector.exe"

        if not injector_path.exists():
            if progress: progress.error("injector not found, run injection first")
            return False

        injector_target = Path(self.wine_prefix) / "drive_c/simple_injector_tmp.exe"
        output_file = Path(self.wine_prefix) / "drive_c/bakkesmod_path.txt"

        try:
            output_file.unlink(missing_ok=True)
            shutil.copy2(injector_path, injector_target)

            cmd = f'{self.loader} "{injector_target}" --get-path'
            run(cmd, wait=True, check=False, env=self.game_env)

            injector_target.unlink(missing_ok=True)

            if not output_file.exists():
                error_msg = "failed to resolve appdata path"
                if progress: progress.error(error_msg)
                print(error_msg)
                return False

            win_path = output_file.read_text(encoding="utf-8").strip().replace("\x00", "")
            output_file.unlink()
            rel_path = win_path_to_linux(win_path)

            self.bakkesmod_path = Path(self.wine_prefix) / "drive_c" / rel_path / "bakkesmod/bakkesmod"
            print(f"resolved bakkesmod path: {self.bakkesmod_path}")
            return True

        except Exception as e:
            print(f"error resolving path: {e}")
            if progress: progress.error(f"error resolving path: {e}")
            return False

    def download_bakkesmod(self, progress):
        progress.status("downloading latest bakkesmod version...")
        temp_location = "/tmp/bakkesmod.zip"

        release_info = self.config.check_bakkesmod_update()
        if not release_info:
            release_info = self.config.get_github_release_info(
                self.config.BAKKESMOD_API, "bakkesmod.zip"
            )

        if not release_info:
            raise RuntimeError("failed to get bakkesmod release info")

        try:
            self._download_file(
                release_info["download_url"],
                temp_location,
                progress,
                "downloading..."
            )

            self.config.set_bakkesmod_version(release_info["version"])
            return temp_location
        except Exception as e:
            raise RuntimeError(f"download failed: {e}")

    def install(self, progress):
        try:
            zip_path = self.download_bakkesmod(progress)

            progress.status("extracting files...")
            BAKKESMOD_LOCATION.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                for member in zip_ref.namelist():
                    is_protected = any(member.startswith(path) for path in PROTECTED_PATHS)
                    target_path = BAKKESMOD_LOCATION / member

                    if is_protected and target_path.exists():
                        continue

                    zip_ref.extract(member, BAKKESMOD_LOCATION)

            progress.status("cleaning up...")
            self.cache_updated = True
            os.remove(zip_path)

        except Exception as e:
            progress.error(str(e))

    def update(self, progress):
        if not BAKKESMOD_LOCATION.exists() or not self.config.get_bakkesmod_version():
            print("updater: bakkesmod cache not found, installing")
            self.install(progress)
            return

        progress.set_status_msg("checking for updates...")

        if not self.config.check_bakkesmod_update():
            progress.done("already on latest version")
            return

        self.install(progress)

    def _get_version(self, location: Path) -> int | None:
        version_path = location / "version.txt"
        try:
            version_str = get_file_content(str(version_path))
            return int(version_str) if version_str else None
        except (ValueError, FileNotFoundError):
            return None

    def _resolve_wine_loader(self, loader_path: str) -> str:
        if loader_path.startswith("/run/host/"):
            return loader_path.replace("/run/host/", "/", 1)
        return loader_path

    def _get_prefix_bakkesmod_path(self):
        if self.bakkesmod_path is None:
            # try to resolve if we have prefix info
            if self.wine_prefix and self.loader:
                self.resolve_install_path()

            if self.bakkesmod_path is None:
                raise RuntimeError("bakkesmod path not resolved (is rocket league running?)")

        return self.bakkesmod_path

    def _download_file(self, url, destination, progress=None, progress_label="downloading..."):
        try:
            res = requests.get(url, stream=True)
            res.raise_for_status()

            total_size = int(res.headers.get("content-length", 0))
            downloaded = 0

            with open(destination, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    downloaded += len(chunk)
                    f.write(chunk)

                    if progress and total_size > 0:
                        percentage = int((downloaded / total_size) * 100)
                        progress.progress(progress_label, percentage)

            return True
        except Exception as e:
            raise RuntimeError(f"download failed: {e}")

    def _check_and_download_injector(self, progress):
        BAKKESMOD_LOCATION.mkdir(parents=True, exist_ok=True)
        injector_path = BAKKESMOD_LOCATION / "simple_injector.exe"

        release_info = self.config.check_injector_update()

        # no update needed
        if not release_info and injector_path.exists():
            return True

        # if we can't check for updates but have the file, use it
        if not release_info:
            print("couldn't get latest injector info, using existing if available")
            return injector_path.exists()

        # download new version
        progress.status("downloading latest injector...")
        try:
            self._download_file(
                release_info["download_url"],
                injector_path,
                progress,
                "downloading injector..."
            )

            self.config.set_injector_version(release_info["version"])
            print(f"injector updated to {release_info['version']}")
            return True

        except Exception as e:
            print(f"failed to download injector: {e}")
            progress.error(f"failed to download injector: {e}")
            return False

    def _ensure_prefix_files(self, progress):
        try:
            prefix_path = self._get_prefix_bakkesmod_path()
        except RuntimeError as e:
            progress.error(str(e))
            return False

        cache_version = self._get_version(BAKKESMOD_LOCATION)

        if cache_version is None:
            progress.error("invalid cached bakkesmod version")
            return False

        if not prefix_path.exists():
            progress.set_status_msg("installing bakkesmod into prefix...")
            copy_tree(BAKKESMOD_LOCATION, prefix_path, SYMLINK_DIRS)
            return True

        prefix_version = self._get_version(prefix_path)

        if prefix_version is None:
            progress.error("invalid bakkesmod version in prefix, please reinstall")
            return False

        if prefix_version != cache_version:
            print(f"bakkesmod version mismatch: prefix={prefix_version}, cache={cache_version}")

            # wait until the user manually updates (just click the button bruh)
            if not self.cache_updated:
                progress.error("bakkesmod version mismatch, please run update")
                return False

            # user updated so lets update the prefix files
            progress.set_status_msg("syncing updated bakkesmod into prefix...")
            copy_tree(BAKKESMOD_LOCATION, prefix_path, SYMLINK_DIRS)
            return True

        return True

    def inject(self, progress):
        if self.injected:
            progress.done("already injected")
            return

        if not self.rl_running:
            progress.error("rocket league process not found")
            return

        if not self.loader:
            progress.error("wine loader not found")
            return

        # verify injector exists before doing anything
        injector_path = BAKKESMOD_LOCATION / "simple_injector.exe"

        if not injector_path.exists():
            progress.progress("downloading injector...", 10)
            if not self._check_and_download_injector(progress):
                progress.error("injector not available")
                return
        else:
            # check for updates in background
            progress.progress("checking injector...", 10)
            self._check_and_download_injector(progress)

        if not self.bakkesmod_path and not self.resolve_install_path(progress):
            return

        # extra validation before injecting
        if not self.wine_prefix or not Path(self.loader).exists():
            progress.error("invalid wine configuration")
            return

        progress.progress("copying bakkesmod files...", 40)

        if not self._ensure_prefix_files(progress):
            return

        injector_path = BAKKESMOD_LOCATION / "simple_injector.exe"

        if not injector_path.exists():
            progress.error("injector binary missing")
            return

        progress.progress("injecting...", 70)

        code, _ = run(
            cmd=f'{self.loader} "{injector_path}"',
            capture=True,
            wait=True,
            check=False,
            env=self.game_env
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
