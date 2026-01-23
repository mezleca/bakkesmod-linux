from PySide6.QtWidgets import QApplication
from gui import BakkesWindow

import sys
import signal

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    window = BakkesWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
