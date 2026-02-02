from getpass import getuser
from pathlib import Path

HOME = str(Path.home())
USER = getuser()

BAKKESMOD_GITHUB_API = "https://api.github.com/repos/bakkesmodorg/BakkesModInjectorCpp/releases/latest"
INJECTOR_GITHUB_LATEST = "https://api.github.com/repos/mezleca/bakkesmod-linux/releases/latest"
BAKKESMOD_LOCATION = Path(f"{HOME}/.local/share/bakkesmod")

PROTECTED_PATHS = [
    "cfg/",
    "plugins/settings/"
]
