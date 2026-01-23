from getpass import getuser
from pathlib import Path

HOME = str(Path.home())
USER = getuser()

BAKKESMOD_GITHUB_LATEST = "https://github.com/bakkesmodorg/BakkesModInjectorCpp/releases/latest/download/bakkesmod.zip"
BAKKESMOD_REPO_API = "https://api.github.com/repos/bakkesmodorg/BakkesModInjectorCpp/releases/latest"
BAKKESMOD_LOCATION = Path(f"{HOME}/.local/share/bakkesmod")
PREFIX_REL_LOCATION = Path("drive_c/users/steamuser/AppData/Roaming/bakkesmod/bakkesmod")

# TOFIX: og injector has 3 other fallbacks
BAKKESMOD_UPDATER_URL = "https://updater.bakkesmod.com/updater"
