"""About dialog for sync67."""

import subprocess
import re
import sys

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from pathlib import Path

from core.version import __version__, __app_name__, __description__, __license__, __author__


def _get_version(cmd, flag='--version', idx=0):
    try:
        r = subprocess.run([cmd, flag], capture_output=True, text=True, timeout=3)
        out = (r.stdout or r.stderr or '').strip()
        m = re.search(r'(\d+\.\d+\.?\d*)', out)
        return m.group(1) if m else ''
    except Exception:
        return ''


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'About {__app_name__}')
        self.setFixedSize(420, 480)
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #e0e0e0; }
            QLabel { color: #e0e0e0; }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Hero image
        img_path = str(Path(__file__).parent.parent / 'assets' / 'about_header.png')
        pixmap = QPixmap(img_path)
        if not pixmap.isNull():
            img = QLabel()
            img.setPixmap(pixmap.scaled(
                380, 160, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(img)

        title = QLabel(__app_name__)
        title.setFont(QFont('', 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        ver = QLabel(f'v{__version__}')
        ver.setFont(QFont('', 11))
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet('color: #888;')
        layout.addWidget(ver)

        layout.addSpacing(10)

        desc = QLabel(__description__)
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(10)

        # Versionen
        pw_ver = _get_version('pipewire')
        ptp_ver = _get_version('ptp4l')
        py_ver = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
        from PyQt6.QtCore import PYQT_VERSION_STR

        versions = QLabel(
            f'<pre style="color: #aaa;">'
            f'PipeWire  {pw_ver or "–":>8}\n'
            f'LinuxPTP  {ptp_ver or "–":>8}\n'
            f'Python    {py_ver:>8}\n'
            f'PyQt6     {PYQT_VERSION_STR:>8}'
            f'</pre>'
        )
        versions.setTextFormat(Qt.TextFormat.RichText)
        versions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(versions)

        layout.addSpacing(10)

        author = QLabel(f'by {__author__}')
        author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author.setStyleSheet('color: #888;')
        layout.addWidget(author)

        lic = QLabel(f'{__license__} License')
        lic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lic.setStyleSheet('color: #666; font-size: 10px;')
        layout.addWidget(lic)

        layout.addSpacing(10)

        btn = QPushButton('OK')
        btn.setFixedWidth(80)
        btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
