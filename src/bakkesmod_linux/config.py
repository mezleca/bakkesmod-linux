import json
import requests

from typing import Any
from bakkesmod_linux.constants import (
    BAKKESMOD_GITHUB_API,
    BAKKESMOD_LOCATION,
    INJECTOR_GITHUB_LATEST
)

DATA_FILE = BAKKESMOD_LOCATION / "data.json"
ReleaseInfo = dict[str, str]

class ConfigManager:
    BAKKESMOD_API = BAKKESMOD_GITHUB_API
    INJECTOR_API = INJECTOR_GITHUB_LATEST

    def __init__(self):
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if not DATA_FILE.exists():
            return {}

        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}

    def _save(self) -> None:
        BAKKESMOD_LOCATION.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def get_bakkesmod_version(self) -> str | None:
        return self.get("bakkesmod_version")

    def set_bakkesmod_version(self, version: str) -> None:
        self.set("bakkesmod_version", version)

    def get_injector_version(self) -> str | None:
        return self.get("injector_version")

    def set_injector_version(self, version: str) -> None:
        self.set("injector_version", version)

    def get_github_release_info(self, api_url: str, asset_name: str) -> ReleaseInfo | None:
        try:
            res = requests.get(api_url, timeout=10)
            res.raise_for_status()
            data = res.json()

            tag_name = data.get("tag_name", "")

            for asset in data.get("assets", []):
                if asset["name"] == asset_name:
                    return {
                        "version": tag_name,
                        "download_url": asset["browser_download_url"]
                    }
            return None
        except requests.RequestException as e:
            print(f"failed to get release info from {api_url}: {e}")
            return None

    def check_bakkesmod_update(self) -> ReleaseInfo | None:
        current = self.get_bakkesmod_version()
        release_info = self.get_github_release_info(BAKKESMOD_GITHUB_API, "bakkesmod.zip")

        if not release_info:
            print("couldnt fetch bakkesmod release info")
            return None

        if current != release_info["version"]:
            print(f"bakkesmod update available: {current} -> {release_info['version']}")
            return release_info

        print(f"bakkesmod is up to date ({current})")
        return None

    def check_injector_update(self) -> ReleaseInfo | None:
        current = self.get_injector_version()
        release_info = self.get_github_release_info(INJECTOR_GITHUB_LATEST, "simple_injector.exe")

        if not release_info:
            print("couldnt fetch injector release info")
            return None

        if current != release_info["version"]:
            print(f"injector update available: {current} -> {release_info['version']}")
            return release_info

        print(f"injector is up to date ({current})")
        return None
