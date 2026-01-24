import sys
import signal
import argparse
import fcntl
import os

from bakkesmod_linux.desktop import create_desktop_entry, remove_desktop_entry
from PySide6.QtWidgets import QApplication
from bakkesmod_linux.gui import BakkesWindow
from bakkesmod_linux.utils import run

def main():
    parser = argparse.ArgumentParser(description="BakkesMod injector for Linux")
    parser.add_argument(
        "--create-desktop",
        action="store_true",
        help="create .desktop for BakkesMod"
    )
    parser.add_argument(
        "--remove-desktop",
        action="store_true",
        help="remove .desktop for BakkesMod"
    )

    args = parser.parse_args()

    from pathlib import Path

    if args.create_desktop:
        exec_path = str(Path(sys.argv[0]).resolve())
        success = create_desktop_entry(exec_path)
        sys.exit(0 if success else 1)

    if args.remove_desktop:
        success = remove_desktop_entry()
        sys.exit(0 if success else 1)

    # check if another instance is running
    lock_file = open(f"/tmp/bakkesmod_{os.getuid()}.lock", "w")

    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        run("notify-send 'BakkesMod' 'BakkesMod is already running!!!'", wait=False)
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    window = BakkesWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
