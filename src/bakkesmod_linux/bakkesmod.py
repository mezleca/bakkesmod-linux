import requests
import zipfile
import shutil
import os

from pathlib import Path
from bakkesmod_linux.constants import (
    BAKKESMOD_GITHUB_LATEST,
    BAKKESMOD_LOCATION,
    BAKKESMOD_UPDATER_URL
)
from bakkesmod_linux.utils import (
    copy_tree,
    get_file_content,
    get_process_env,
    get_resource_path,
    run,
    filter_game_env,
    win_path_to_linux
)

SYMLINK_DIRS = ["cfg", "plugins"]
WATCHER_INTERVAL_MS = 3000

class BakkesHelper:
    def __init__(self):
        self.injected = False
        self.wine_prefix = None
        self.rl_process = None
        self.loader = None
        self.cache_updated = False
        self.rl_running = False
        self.bakkesmod_path = None
        self.game_env = None
        self._on_process_change = None

    def set_process_callback(self, callback):
        self._on_process_change = callback

    def check_rl_process(self) -> None:
        result = get_process_env("RocketLeague.exe")

        was_running = self.rl_running
        self.rl_running = result is not None

        if self.rl_running and result:
            _, env = result
            self.wine_prefix = env["WINEPREFIX"]
            self.loader = self.resolve_wine_loader(env["WINELOADER"])
            self.game_env = filter_game_env(env)

            if not self.bakkesmod_path:
                self.resolve_install_path()

        # reset injection state when process dies
        if was_running and not self.rl_running:
            self.injected = False

        # notify ui about state change
        if self._on_process_change and was_running != self.rl_running:
            self._on_process_change(self.rl_running)

    def resolve_install_path(self, progress=None) -> bool:
        if not self.wine_prefix or not self.loader:
            return False

        injector_target = Path(self.wine_prefix) / "drive_c/simple_injector_tmp.exe"
        output_file = Path(self.wine_prefix) / "drive_c/bakkesmod_path.txt"

        try:
            if output_file.exists():
                output_file.unlink()

            with get_resource_path("simple_injector.exe") as src:
                shutil.copy2(src, injector_target)

            cmd = f'{self.loader} "{injector_target}" --get-path'
            _ = run(cmd, wait=True, check=False, env=self.game_env)

            if injector_target.exists():
                injector_target.unlink()

            if not output_file.exists():
                error_msg = "failed to resolve appdata path"
                if progress: progress.error(error_msg)
                print(error_msg)
                return False

            win_path = output_file.read_text(encoding="utf-8").strip().replace("\x00", "")
            output_file.unlink()

            # converts C:\Users\SteamUser\AppData... -> drive_c/users/steamuser/appdata...
            rel_path = win_path_to_linux(win_path)
            self.bakkesmod_path = Path(self.wine_prefix) / "drive_c" / rel_path / "bakkesmod/bakkesmod"
            print(f"resolved bakkesmod path: {self.bakkesmod_path}")
            return True

        except Exception as e:
            print(f"error resolving path: {e}")
            if progress: progress.error(f"error resolving path: {e}")
            return False

    def download_bakkesmod(self, progress) -> str:
        progress.status("downloading latest bakkesmod version...")
        temp_location = "/tmp/bakkesmod.zip"

        try:
            res = requests.get(BAKKESMOD_GITHUB_LATEST, stream=True)
            res.raise_for_status()

            total_size = int(res.headers.get("content-length", 0))
            downloaded = 0

            with open(temp_location, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    downloaded += len(chunk)
                    f.write(chunk)

                    if total_size > 0:
                        percentage = int((downloaded / total_size) * 100)
                        progress.progress("downloading...", percentage)

            return temp_location
        except Exception as e:
            raise RuntimeError(f"download failed: {e}")

    def install(self, progress):
        try:
            zip_path = self.download_bakkesmod(progress)

            progress.status("extracting files...")
            BAKKESMOD_LOCATION.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(BAKKESMOD_LOCATION)

            progress.status("cleaning up...")
            self.cache_updated = True
            os.remove(zip_path)

        except Exception as e:
            progress.error(str(e))

    def update(self, progress):
        if not BAKKESMOD_LOCATION.exists():
            print("updater: bakkesmod cache not found, installing")
            self.install(progress)
            return

        current_version = self.get_current_version(BAKKESMOD_LOCATION)

        if current_version is None:
            print("updater: invalid cache version, reinstalling")
            self.install(progress)
            return

        progress.set_status_msg("checking for updates...")

        if not self.check_version_mismatch(current_version):
            progress.done("already on latest version")
            return

        self.install(progress)

    def get_current_version(self, location: Path) -> int | None:
        version_path = location / "version.txt"

        try:
            version_str = get_file_content(str(version_path))
            return int(version_str) if version_str else None
        except ValueError:
            return None

    def get_bakkesmod_updater_data(self, version: int) -> str | None:
        try:
            res = requests.get(f"{BAKKESMOD_UPDATER_URL}/{version}", timeout=5)
            if res.status_code == 200:
                data = res.json()
                return data.get("update_info")
        except requests.RequestException:
            print("failed to check for updates")
        return None

    def check_version_mismatch(self, current_version: int) -> bool:
        print(f"checking version: {current_version}")
        data = self.get_bakkesmod_updater_data(current_version)
        return data is not None

    def resolve_wine_loader(self, loader_path: str) -> str:
        if loader_path.startswith("/run/host/"):
            return loader_path.replace("/run/host/", "/", 1)
        return loader_path

    def get_prefix_bakkesmod_path(self) -> Path:
        if self.bakkesmod_path is None:
            # try to resolve if we have prefix info
            if self.wine_prefix and self.loader:
                self.resolve_install_path()

            if self.bakkesmod_path is None:
                raise RuntimeError("bakkesmod path not resolved (is rocket league running?)")

        return self.bakkesmod_path

    def ensure_prefix_files(self, progress) -> bool:
        try:
            prefix_path = self.get_prefix_bakkesmod_path()
        except RuntimeError as e:
            progress.error(str(e))
            return False

        cache_version = self.get_current_version(BAKKESMOD_LOCATION)

        if cache_version is None:
            progress.error("invalid cached bakkesmod version")
            return False

        if not prefix_path.exists():
            progress.set_status_msg("installing bakkesmod into prefix...")
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
            progress.set_status_msg("syncing updated bakkesmod into prefix...")
            copy_tree(BAKKESMOD_LOCATION, prefix_path, SYMLINK_DIRS)
            return True

        return True

    def inject(self, progress):
        if self.injected:
            progress.done("already injected")
            return

        if not self.loader:
            progress.error("wine loader not found")
            return

        if not self.rl_running:
            progress.error("rocket league process not found")
            return

        if not self.bakkesmod_path and not self.resolve_install_path(progress):
            return

        # extra validation before injecting
        if not self.wine_prefix or not Path(self.loader).exists():
            progress.error("invalid wine configuration")
            return

        progress.progress("copying bakkesmod files...", 20)

        # ensure bakkesmod files inside prefix
        if not self.ensure_prefix_files(progress):
            return

        with get_resource_path("simple_injector.exe") as injector_path:
            if not injector_path.exists():
                progress.error("injector binary missing")
                return

            progress.progress("injecting...", 50)

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
