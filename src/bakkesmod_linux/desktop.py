import shutil

from pathlib import Path
from bakkesmod_linux.utils import get_resource_path

DESKTOP_ENTRY = """[Desktop Entry]
Name=BakkesMod
Comment=BakkesMod injector for Linux
Exec={exec_path}
Icon={icon_path}
Terminal=false
Type=Application
Categories=Game;Utility;
Keywords=bakkesmod;rocket league;mod;
"""

ICON_DEST = Path.home() / ".local/share/icons/bakkesmod.png"
DESKTOP_DEST = Path.home() / ".local/share/applications/bakkesmod.desktop"

def ensure_icon() -> Path:
    if ICON_DEST.exists():
        return ICON_DEST

    ICON_DEST.parent.mkdir(parents=True, exist_ok=True)

    with get_resource_path("bakkesmod.png") as icon_src:
        shutil.copy2(icon_src, ICON_DEST)

    return ICON_DEST

def create_desktop_entry(exec_path: str) -> bool:
    try:
        icon_path = ensure_icon()
        content = DESKTOP_ENTRY.format(
            icon_path=icon_path,
            exec_path=exec_path
        )

        DESKTOP_DEST.parent.mkdir(parents=True, exist_ok=True)
        DESKTOP_DEST.write_text(content, encoding="utf-8")

        print(f"created desktop entry at: {DESKTOP_DEST}")
        return True
    except Exception as e:
        print(f"failed to create desktop entry: {e}")
        return False

def desktop_entry_exists() -> bool:
    return DESKTOP_DEST.exists()

def remove_desktop_entry() -> bool:
    try:
        if DESKTOP_DEST.exists():
            DESKTOP_DEST.unlink()
            print(f"removed desktop entry: {DESKTOP_DEST}")

        if ICON_DEST.exists():
            ICON_DEST.unlink()
            print(f"removed icon: {ICON_DEST}")

        return True
    except Exception as e:
        print(f"failed to remove desktop entry: {e}")
        return False
