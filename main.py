#!/usr/bin/env python3
"""
Main entry point for sync67 application.
"""
import os
import sys

def main():
    if os.getuid() != 0:
        print("sync67 requires root privileges.", file=sys.stderr)
        print("Please run: sudo python3 main.py", file=sys.stderr)
        sys.exit(1)

    from PyQt6.QtWidgets import QApplication
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()