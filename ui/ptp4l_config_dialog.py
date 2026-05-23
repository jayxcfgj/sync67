"""PTP4L Config Editor Dialog – 7 tabs for /etc/linuxptp/ptp4l.conf."""

import subprocess
import re
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QPushButton,
    QFormLayout, QWidget, QScrollArea, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import QPalette, QColor, QRegularExpressionValidator, QFont

from core.ptp4l_config import PTP4LConfig, format_value, _KV_RE
from core.ptp4l_config_meta import (
    CONFIG_PARAMS, PARAM_MAP, SECTION_ORDER, get_params_for_section
)
from PyQt6.QtWidgets import QApplication


# ── Widget Factory ────────────────────────────────────────────

class ParamWidget:
    def __init__(self, param_def, widget, default_label):
        self.defn = param_def
        self.widget = widget
        self.default_label = default_label

    def get_value(self):
        raise NotImplementedError

    def set_value(self, value):
        raise NotImplementedError

    def mark_deviation(self, is_deviation):
        if is_deviation:
            self.widget.setStyleSheet(
                'background-color: #3a3a3a; border-left: 3px solid #f0c040;'
            )
        else:
            self.widget.setStyleSheet('')


class BoolWidget(ParamWidget):
    def get_value(self):
        return 1 if self.widget.isChecked() else 0

    def set_value(self, value):
        self.widget.setChecked(bool(int(value)) if value is not None else False)


class IntWidget(ParamWidget):
    def get_value(self):
        return self.widget.value()

    def set_value(self, value):
        self.widget.setValue(int(value) if value is not None else 0)


class FloatWidget(ParamWidget):
    def get_value(self):
        return self.widget.value()

    def set_value(self, value):
        self.widget.setValue(float(value) if value is not None else 0.0)


class ChoiceWidget(ParamWidget):
    def get_value(self):
        return self.widget.currentData()

    def set_value(self, value):
        idx = self.widget.findData(str(value))
        if idx >= 0:
            self.widget.setCurrentIndex(idx)
        else:
            self.widget.setCurrentText(str(value))


class StringWidget(ParamWidget):
    def get_value(self):
        return self.widget.text()

    def set_value(self, value):
        self.widget.setText(str(value) if value is not None else '')


def create_widget(param_def, current_value, on_change=None):
    ptype = param_def.type
    tooltip = param_def.tooltip

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    label = QLabel(param_def.label)
    label.setToolTip(tooltip)
    layout.addWidget(label)

    if param_def.type == 'bool':
        dv = param_def.default
        if isinstance(dv, bool):
            default_text = 'Default: checked' if dv else 'Default: unchecked'
        elif isinstance(dv, int):
            default_text = 'Default: checked' if dv else 'Default: unchecked'
        else:
            default_text = 'Default: checked' if str(dv) in ('1', 'true', 'True') else 'Default: unchecked'
    else:
        default_text = f'Default: {param_def.default}' if param_def.default is not None else ''
    default_label = QLabel(default_text)
    default_label.setStyleSheet('color: gray; font-size: 10px;')

    if ptype == 'bool':
        w = QCheckBox()
        w.setToolTip(tooltip)
        pw = BoolWidget(param_def, w, default_label)
    elif ptype == 'int':
        w = QSpinBox()
        w.setToolTip(tooltip)
        if param_def.min_val is not None:
            w.setMinimum(param_def.min_val)
        else:
            w.setMinimum(-999999)
        if param_def.max_val is not None:
            w.setMaximum(param_def.max_val)
        else:
            w.setMaximum(999999)
        if param_def.step is not None:
            w.setSingleStep(param_def.step)
        pw = IntWidget(param_def, w, default_label)
    elif ptype == 'float':
        w = QDoubleSpinBox()
        w.setToolTip(tooltip)
        if param_def.min_val is not None:
            w.setMinimum(param_def.min_val)
        else:
            w.setMinimum(-999999.0)
        if param_def.max_val is not None:
            w.setMaximum(param_def.max_val)
        else:
            w.setMaximum(999999.0)
        if param_def.step is not None:
            w.setSingleStep(param_def.step)
        w.setDecimals(4)
        pw = FloatWidget(param_def, w, default_label)
    elif ptype == 'choice':
        w = QComboBox()
        w.setToolTip(tooltip)
        w.setMinimumWidth(200)
        for c in param_def.choices:
            if isinstance(c, tuple):
                w.addItem(c[1], c[0])
            else:
                w.addItem(str(c), c)
        pw = ChoiceWidget(param_def, w, default_label)
    elif ptype == 'string':
        w = QLineEdit()
        w.setToolTip(tooltip)
        w.setMinimumWidth(250)
        pw = StringWidget(param_def, w, default_label)
    else:
        w = QLineEdit()
        w.setToolTip(tooltip)
        pw = StringWidget(param_def, w, default_label)

    if current_value is not None:
        pw.set_value(current_value)

    layout.addWidget(w)
    layout.addWidget(default_label)

    def check_deviation():
        try:
            current = pw.get_value()
            default = param_def.default
            is_dev = str(current) != str(default)
            pw.mark_deviation(is_dev)
            if on_change:
                on_change()
        except Exception:
            pass

    if isinstance(w, QLineEdit):
        w.textChanged.connect(check_deviation)
    elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
        w.valueChanged.connect(check_deviation)
    elif isinstance(w, QCheckBox):
        w.stateChanged.connect(check_deviation)
    elif isinstance(w, QComboBox):
        w.currentIndexChanged.connect(check_deviation)

    check_deviation()

    return container, pw


# ─── Hauptdialog ──────────────────────────────────────────────

class PTP4LConfigDialog(QDialog):
    def __init__(self, config: PTP4LConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.widgets = {}
        self._has_changes = False
        self.setWindowTitle('PTP4L Config Editor')
        self.setMinimumSize(480, 300)
        self.resize(700, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self._apply_dark_theme()
        self._init_ui()

    def _apply_dark_theme(self):
        app = QApplication.instance()
        if app:
            pal = QPalette()
            pal.setColor(QPalette.ColorRole.Window, QColor('#2b2b2b'))
            pal.setColor(QPalette.ColorRole.WindowText, QColor('#e0e0e0'))
            pal.setColor(QPalette.ColorRole.Base, QColor('#1e1e1e'))
            pal.setColor(QPalette.ColorRole.Button, QColor('#3c3c3c'))
            pal.setColor(QPalette.ColorRole.ButtonText, QColor('#e0e0e0'))
            pal.setColor(QPalette.ColorRole.Text, QColor('#e0e0e0'))
            pal.setColor(QPalette.ColorRole.Highlight, QColor('#4a9eff'))
            pal.setColor(QPalette.ColorRole.HighlightedText, QColor('#ffffff'))
            app.setPalette(pal)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        tab_style = """
            QTabWidget::pane { background-color: #2b2b2b; border: 1px solid #555; }
            QTabBar::tab { background-color: #3c3c3c; color: #e0e0e0; padding: 6px 14px;
                border: 1px solid #555; border-bottom: none; }
            QTabBar::tab:selected { background-color: #2b2b2b; }
            QTabBar::tab:hover:!selected { background-color: #4a4a4a; }
        """
        self.tabs.setStyleSheet(tab_style)

        tab_names = {'Quick': '⚡ Quick', 'Default': 'Main', 'Port': 'Port',
                     'Runtime': 'Runtime', 'Servo': 'Servo',
                     'Transport': 'Transport', 'Interface': 'Interface'}

        for section in SECTION_ORDER:
            self._create_tab(section, tab_names.get(section, section))
        self._create_other_tab()

        self._has_changes = False  # initial loading should not mark as changed

        layout.addWidget(self.tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        apply_btn = QPushButton('Apply')
        apply_btn.clicked.connect(self._on_apply)
        apply_btn.setMinimumWidth(100)

        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self._on_cancel)
        cancel_btn.setMinimumWidth(100)

        reset_btn = QPushButton('Reset Config')
        reset_btn.clicked.connect(self._on_reset)
        reset_btn.setMinimumWidth(100)

        for btn in (apply_btn, cancel_btn, reset_btn):
            btn.setStyleSheet("""
                QPushButton { background-color: #3c3c3c; color: #e0e0e0;
                    border: 1px solid #555; border-radius: 4px; padding: 5px 14px; }
                QPushButton:hover { background-color: #4a4a4a; }
            """)

        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(reset_btn)
        layout.addLayout(btn_layout)

    def _create_tab(self, section, tab_label):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setMinimumSize(0, 0)
        form = QFormLayout(content)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        params = get_params_for_section(section)
        for pdef in params:
            val = self.config.get(pdef.key)
            container, pw = create_widget(pdef, val, on_change=self._mark_changes)
            self.widgets[pdef.key] = pw

            supported = self.config._supported is None or pdef.key in self.config._supported
            if not supported:
                container.setEnabled(False)
                label = container.layout().itemAt(0).widget()
                if isinstance(label, QLabel):
                    label.setText(f"{pdef.label} (unsupported)")
                    label.setStyleSheet("color: #ff6b6b;")

            form.addRow(container)

        scroll.setWidget(content)
        self.tabs.addTab(scroll, tab_label)

    def _create_other_tab(self):
        meta_keys = {p.key for p in CONFIG_PARAMS}
        if self.config._supported is None:
            unknown = []
        else:
            unknown = sorted(self.config._supported - meta_keys)

        content = QWidget()
        content.setMinimumSize(0, 0)
        layout = QVBoxLayout(content)

        if not unknown:
            label = QLabel("All binary parameters are already covered in the existing tabs.")
            label.setStyleSheet("color: gray; padding: 20px;")
            layout.addWidget(label)
            self._other_text = None
        else:
            label = QLabel(
                f"These {len(unknown)} parameter(s) are known to ptp4l "
                "but not yet in our editor.\n"
                "Edit them as key<tab>value pairs (one per line):"
            )
            label.setWordWrap(True)
            layout.addWidget(label)

            self._other_text = QTextEdit()
            self._other_text.setFont(QFont("Courier New", 10))
            self._other_text.setMaximumHeight(300)
            self._other_text.setStyleSheet(
                "QTextEdit { background-color: #1e1e1e; color: #e0e0e0; "
                "border: 1px solid #555; }"
            )

            # Pre-populate with any values already in the config
            lines = []
            for key in unknown:
                val = self.config.get(key)
                if val is not None:
                    lines.append(f"{key}\t{format_value(val)}")
            if not lines:
                lines = unknown
            self._other_text.setPlainText('\n'.join(lines))

            layout.addWidget(self._other_text)

        self.tabs.addTab(content, "🔮 Other")

    def _on_apply(self):
        try:
            skipped = []
            for key, pw in self.widgets.items():
                pdef = pw.defn
                try:
                    value = pw.get_value()
                except Exception:
                    continue
                # Handle SlaveOnly/MasterOnly as bool-int
                if isinstance(value, bool):
                    value = 1 if value else 0
                if not self.config.set(pdef.key, value):
                    if (self.config._supported is not None
                            and pdef.key not in self.config._supported):
                        skipped.append(pdef.key)

            # Parse Other tab params
            if self._other_text is not None:
                for line in self._other_text.toPlainText().split('\n'):
                    line = line.strip()
                    m = _KV_RE.match(line)
                    if m:
                        key, val = m.group(1), m.group(2).strip()
                        self.config.set(key, val)

            self.config.save()

            msg = 'Config saved.'
            if skipped:
                msg += (f'\n\n{len(skipped)} parameter(s) were skipped '
                        '(not supported by your ptp4l version):\n'
                        + ', '.join(skipped))
            QMessageBox.information(self, 'Success', msg)
            self._has_changes = False
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Config could not be saved:\n{e}')

    def _on_cancel(self):
        if self._has_changes:
            reply = QMessageBox.question(
                self, 'Discard changes?',
                'There are unsaved changes. Close anyway?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.reject()

    def _on_reset(self):
        reply = QMessageBox.warning(
            self, 'Reset Config',
            'Are you sure? This will replace your config with\n'
            'the default config. A backup will be saved as .bak.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.config.reset_to_default()
            self.config.load(self.config.get_loaded_path())
            QMessageBox.information(self, 'Reset', 'Config reset to Default.')
            self._reload_widgets()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Reset failed:\n{e}')

    def _mark_changes(self):
        self._has_changes = True

    def _reload_widgets(self):
        for key, pw in self.widgets.items():
            val = self.config.get(key)
            if val is not None:
                pw.set_value(val)
        self._has_changes = False
