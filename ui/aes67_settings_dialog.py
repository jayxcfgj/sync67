"""AES67 Config Editor Dialog – 4 Tabs mit dynamischen Widgets."""

import os
import subprocess
import re

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QTextEdit, QPushButton,
    QGroupBox, QFormLayout, QWidget, QScrollArea,
    QMessageBox, QGridLayout, QApplication
)
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator, QPalette, QColor

from core.aes67_config import AES67Config
from core.aes67_config_meta import (
    CONFIG_PARAMS, PARAM_MAP,
    get_params_for_section, SECTION_ORDER
)


# ── Hilfsfunktionen ────────────────────────────────────────────

_IFACE_CACHE = None

def _load_interfaces():
    """Liste der Netzwerk-Interfaces (ohne lo) – gecached."""
    global _IFACE_CACHE
    if _IFACE_CACHE is not None:
        return _IFACE_CACHE
    try:
        result = subprocess.run(['ip', 'link', 'show'],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            ifaces = re.findall(r'^\d+: (\w+):', result.stdout, re.MULTILINE)
            _IFACE_CACHE = [i for i in ifaces if i != 'lo']
            return _IFACE_CACHE
    except Exception:
        pass
    _IFACE_CACHE = []
    return _IFACE_CACHE


def _strip_quotes(s):
    if isinstance(s, str) and s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    return s


def _add_quotes(s):
    s = str(s)
    if not s.startswith('"'):
        return f'"{s}"'
    return s


# ── Widget Factory ─────────────────────────────────────────────

class ParamWidget:
    """Wrapper für ein Parameter-Widget + Default-Anzeige."""

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


class StringWidget(ParamWidget):
    def get_value(self):
        return self.widget.text()

    def set_value(self, value):
        if isinstance(value, str) and value.startswith('"'):
            value = value[1:-1]
        self.widget.setText(str(value))


class IntWidget(ParamWidget):
    def get_value(self):
        return self.widget.value()

    def set_value(self, value):
        self.widget.setValue(int(value))


class FloatWidget(ParamWidget):
    def get_value(self):
        return self.widget.value()

    def set_value(self, value):
        self.widget.setValue(float(value))


class BoolWidget(ParamWidget):
    def get_value(self):
        return self.widget.isChecked()

    def set_value(self, value):
        if isinstance(value, str):
            value = value.lower() == 'true'
        self.widget.setChecked(bool(value))


class ChoiceWidget(ParamWidget):
    def get_value(self):
        text = self.widget.currentText()
        # Try to parse back to original type
        if text == '':
            return None
        try:
            if '.' in text:
                return float(text)
            return int(text)
        except ValueError:
            return _add_quotes(text) if ' ' in text else text

    def set_value(self, value):
        idx = -1
        val_str = str(value).strip('"')
        for i in range(self.widget.count()):
            item = self.widget.itemText(i)
            if item == val_str or item == str(value):
                idx = i
                break
        if idx >= 0:
            self.widget.setCurrentIndex(idx)


class IpWidget(ParamWidget):
    def get_value(self):
        return self.widget.text()

    def set_value(self, value):
        if isinstance(value, str) and value.startswith('"'):
            value = value[1:-1]
        self.widget.setText(str(value))


class PortWidget(ParamWidget):
    def get_value(self):
        return self.widget.value()

    def set_value(self, value):
        self.widget.setValue(int(value))


class MultilineWidget(ParamWidget):
    def get_value(self):
        text = self.widget.toPlainText().strip()
        if text.startswith('[') and text.endswith(']'):
            inner = text[1:-1]
            items = [item.strip().strip('"') for item in inner.split(',') if item.strip()]
            return '[' + ', '.join(f'"{item}"' if ' ' in item else item for item in items) + ']'
        return text

    def set_value(self, value):
        if isinstance(value, list):
            display = ', '.join(str(v).strip('"') for v in value)
            self.widget.setPlainText(display)
        elif isinstance(value, str):
            display = value.strip('"').strip('[').strip(']')
            self.widget.setPlainText(display)
        else:
            self.widget.setPlainText(str(value))


def create_widget(param_def, current_value):
    """Create the appropriate widget for a parameter definition."""
    ptype = param_def.type
    label_text = param_def.label
    tooltip = param_def.tooltip

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    # Label
    label = QLabel(label_text)
    label.setToolTip(tooltip)
    layout.addWidget(label)

    # Default value display
    default_text = f'Default: {param_def.default}' if param_def.default is not None else ''
    default_label = QLabel(default_text)
    default_label.setStyleSheet('color: gray; font-size: 10px;')
    default_label.setToolTip(tooltip)

    # Widget
    if ptype == 'string':
        w = QLineEdit()
        w.setToolTip(tooltip)
        w.setMinimumWidth(200)
        pw = StringWidget(param_def, w, default_label)

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
        w.setDecimals(2)
        pw = FloatWidget(param_def, w, default_label)

    elif ptype == 'bool':
        w = QCheckBox()
        w.setToolTip(tooltip)
        pw = BoolWidget(param_def, w, default_label)

    elif ptype == 'choice':
        w = QComboBox()
        w.setToolTip(tooltip)
        w.setMinimumWidth(200)
        for choice in param_def.choices:
            display = str(choice).strip('"')
            w.addItem(display, choice)
        pw = ChoiceWidget(param_def, w, default_label)

    elif ptype == 'interface':
        w = QComboBox()
        w.setToolTip(tooltip)
        w.setMinimumWidth(200)
        w.addItems(_load_interfaces())
        pw = ChoiceWidget(param_def, w, default_label)

    elif ptype == 'ip':
        w = QLineEdit()
        w.setToolTip(tooltip)
        w.setMinimumWidth(200)
        ip_regex = QRegularExpression(
            r'^(\d{1,3}\.){3}\d{1,3}$'
        )
        w.setValidator(QRegularExpressionValidator(ip_regex))
        pw = IpWidget(param_def, w, default_label)

    elif ptype == 'port':
        w = QSpinBox()
        w.setToolTip(tooltip)
        w.setMinimum(1)
        w.setMaximum(65535)
        pw = PortWidget(param_def, w, default_label)

    elif ptype == 'multiline':
        w = QTextEdit()
        w.setToolTip(tooltip)
        w.setMaximumHeight(60)
        w.setMinimumWidth(200)
        pw = MultilineWidget(param_def, w, default_label)

    else:
        w = QLineEdit()
        w.setToolTip(tooltip)
        pw = StringWidget(param_def, w, default_label)

    # Set current value
    if current_value is not None:
        pw.set_value(current_value)

    layout.addWidget(w)
    layout.addWidget(default_label)

    # Deviation tracking
    def check_deviation():
        try:
            current = pw.get_value()
        except Exception:
            return
        default = param_def.default
        is_dev = str(current) != str(default)
        pw.mark_deviation(is_dev)

    # Connect change signal
    if isinstance(w, QLineEdit):
        w.textChanged.connect(check_deviation)
    elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
        w.valueChanged.connect(check_deviation)
    elif isinstance(w, QCheckBox):
        w.stateChanged.connect(check_deviation)
    elif isinstance(w, QComboBox):
        w.currentIndexChanged.connect(check_deviation)
    elif isinstance(w, QTextEdit):
        w.textChanged.connect(check_deviation)

    # Initial check
    check_deviation()

    return container, pw


# ── RTP Sink Tab Widget (Multi-Instanz) ────────────────────────

class RtpSinkTabWidget(QWidget):
    """Einzelner Tab für eine rtp-sink Instanz."""

    def __init__(self, config, sink_index, parent=None):
        super().__init__(parent)
        self.config = config
        self.sink_index = sink_index
        self.widgets = {}  # key → ParamWidget
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        sink_params = [p for p in CONFIG_PARAMS
                       if p.section == 'RTP Sink Output'
                       and p.module == 'libpipewire-module-rtp-sink']

        for pdef in sink_params:
            keys = ('context.modules', self.sink_index) + pdef.path
            val = self.config.get(*keys)
            container, pw = create_widget(pdef, val)
            self.widgets[pdef.key] = pw
            form.addRow(container)

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def collect_values(self):
        values = {}
        for key, pw in self.widgets.items():
            try:
                values[key] = pw.get_value()
            except Exception:
                pass
        return values


# ── Hauptdialog ────────────────────────────────────────────────

class AES67SettingsDialog(QDialog):
    """Config-Editor für pipewire-aes67.conf."""

    def __init__(self, config: AES67Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.widgets: dict[str, ParamWidget] = {}
        self.rtp_sink_tabs = []
        self.system_clock_cb = None
        self._has_changes = False

        self.setWindowTitle('AES67 Config Editor')
        self.setMinimumSize(650, 550)
        self.resize(700, 600)
        self._init_ui()

    def _apply_dark_theme(self):
        app = QApplication.instance()
        if app:
            pal = QPalette()
            pal.setColor(QPalette.ColorRole.Window, QColor('#2b2b2b'))
            pal.setColor(QPalette.ColorRole.WindowText, QColor('#e0e0e0'))
            pal.setColor(QPalette.ColorRole.Base, QColor('#1e1e1e'))
            pal.setColor(QPalette.ColorRole.AlternateBase, QColor('#353535'))
            pal.setColor(QPalette.ColorRole.ToolTipBase, QColor('#1e1e1e'))
            pal.setColor(QPalette.ColorRole.ToolTipText, QColor('#e0e0e0'))
            pal.setColor(QPalette.ColorRole.Text, QColor('#e0e0e0'))
            pal.setColor(QPalette.ColorRole.Button, QColor('#3c3c3c'))
            pal.setColor(QPalette.ColorRole.ButtonText, QColor('#e0e0e0'))
            pal.setColor(QPalette.ColorRole.BrightText, QColor('#ff6b6b'))
            pal.setColor(QPalette.ColorRole.Link, QColor('#4a9eff'))
            pal.setColor(QPalette.ColorRole.Highlight, QColor('#4a9eff'))
            pal.setColor(QPalette.ColorRole.HighlightedText, QColor('#ffffff'))
            app.setPalette(pal)

        tab_style = """
            QTabWidget::pane {
                background-color: #2b2b2b;
                border: 1px solid #555;
            }
            QTabBar::tab {
                background-color: #3c3c3c;
                color: #e0e0e0;
                padding: 6px 14px;
                border: 1px solid #555;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #2b2b2b;
                border-bottom: 1px solid #2b2b2b;
            }
            QTabBar::tab:hover:!selected {
                background-color: #4a4a4a;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e1e;
                color: #e0e0e0;
                selection-background-color: #4a9eff;
            }
            QToolTip {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #666;
                padding: 4px 6px;
                font-size: 12px;
                border-radius: 3px;
            }
        """
        self.tabs.setStyleSheet(tab_style)

        btn_style = """
            QPushButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px 14px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border-color: #777;
            }
            QPushButton:pressed {
                background-color: #555;
            }
        """
        self.apply_btn.setStyleSheet(btn_style)
        self.cancel_btn.setStyleSheet(btn_style)
        self.reset_btn.setStyleSheet(btn_style)

        scroll_style = """
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 10px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #555;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #777;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """
        for scroll in self.findChildren(QScrollArea):
            scroll.setStyleSheet(scroll_style)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # TabWidget
        self.tabs = QTabWidget()
        self._create_ptp_tab()
        self._create_sap_tab()
        self._create_sink_tab()
        self._create_expert_tab()
        layout.addWidget(self.tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.apply_btn = QPushButton('Apply')
        self.apply_btn.clicked.connect(self._on_apply)
        self.apply_btn.setMinimumWidth(100)

        self.cancel_btn = QPushButton('Cancel')
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setMinimumWidth(100)

        self.reset_btn = QPushButton('Reset Config')
        self.reset_btn.clicked.connect(self._on_reset)
        self.reset_btn.setMinimumWidth(100)

        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.reset_btn)
        layout.addLayout(btn_layout)

        self._apply_dark_theme()

    # ── Tab-Erstellung ──────────────────────────────────────────

    def _create_ptp_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        params = get_params_for_section('PTP Clock')
        for pdef in params:
            if pdef.key == 'system.clock.enabled':
                continue
            keys = ('context.objects', 0) + pdef.path
            val = self.config.get(*keys)
            container, pw = create_widget(pdef, val)
            form.addRow(container)
            self.widgets[pdef.key] = pw

        # System-Clock Checkbox (special handling)
        self.system_clock_cb = QCheckBox('System-Clock verwenden (PHC deaktivieren)')
        self.system_clock_cb.setToolTip(
            'Wenn aktiviert: clock.interface wird auskommentiert.\n'
            'Die System-Clock wird statt der PHC verwendet.\n'
            'Nötig wenn die App als root läuft und PHC Timestamp 0 liefert.'
        )
        # Check if clock.interface is currently commented out
        is_commented = self._is_clock_interface_commented()
        self.system_clock_cb.setChecked(is_commented)
        self.system_clock_cb.stateChanged.connect(self._mark_changes)
        form.addRow(self.system_clock_cb)

        scroll.setWidget(content)
        self.tabs.addTab(scroll, 'PTP Clock')

    def _create_sap_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        params = get_params_for_section('RTP SAP Input')
        for pdef in params:
            keys = ('context.modules', pdef.module) + pdef.path
            val = self.config.get(*keys)
            container, pw = create_widget(pdef, val)
            form.addRow(container)
            self.widgets[pdef.key] = pw

        scroll.setWidget(content)
        self.tabs.addTab(scroll, 'RTP SAP Input')

    def _create_sink_tab(self):
        """RTP Sink Output Tab mit Multi-Instanz-Unterstützung."""
        # Container with sink tab widget and add/remove buttons
        container = QWidget()
        layout = QVBoxLayout(container)

        self.sink_tab_widget = QTabWidget()
        self._rebuild_sink_tabs()
        layout.addWidget(self.sink_tab_widget)

        btn_layout = QHBoxLayout()
        self.add_sink_btn = QPushButton('+ Add Sink')
        self.add_sink_btn.clicked.connect(self._on_add_sink)
        self.remove_sink_btn = QPushButton('✕ Remove Sink')
        self.remove_sink_btn.clicked.connect(self._on_remove_sink)
        btn_layout.addWidget(self.add_sink_btn)
        btn_layout.addWidget(self.remove_sink_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.tabs.addTab(container, 'RTP Sink Output')

    def _rebuild_sink_tabs(self):
        """Rebuild the sink tab widget from config modules."""
        self.sink_tab_widget.clear()
        self.rtp_sink_tabs = []
        modules = self.config._data.get('context.modules', [])
        for idx, mod in enumerate(modules):
            if isinstance(mod, dict) and mod.get('name') == 'libpipewire-module-rtp-sink':
                tab = RtpSinkTabWidget(self.config, idx)
                self.sink_tab_widget.addTab(tab, f'Sink {len(self.rtp_sink_tabs) + 1}')
                self.rtp_sink_tabs.append(tab)

    def _create_expert_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        # Advanced parameter widgets
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        for pdef in CONFIG_PARAMS:
            if not pdef.advanced:
                continue
            if pdef.module == 'context.objects':
                keys = ('context.objects', 0) + pdef.path
            else:
                keys = ('context.modules', pdef.module) + pdef.path
            val = self.config.get(*keys)
            container, pw = create_widget(pdef, val)
            form.addRow(container)
            self.widgets[pdef.key] = pw
        layout.addLayout(form)

        # ── stream.rules Raw Editor ────────────────────────────
        rules_group = QGroupBox('stream.rules (Raw)')
        rules_layout = QVBoxLayout(rules_group)

        rules_label = QLabel(
            'Bearbeite die SAP-Stream-Regeln direkt im SPA-Format.\n'
            'Änderungen werden beim Apply übernommen.'
        )
        rules_label.setWordWrap(True)
        rules_layout.addWidget(rules_label)

        self.rules_editor = QTextEdit()
        self.rules_editor.setMinimumHeight(200)
        self.rules_editor.setStyleSheet(
            'font-family: "Courier New", monospace; font-size: 11px;'
        )
        rules_layout.addWidget(self.rules_editor)

        # Load current stream.rules raw text
        _, _, rules_text = self.config.get_raw_block(
            'context.modules', 'libpipewire-module-rtp-sap', 'args', 'stream.rules'
        )
        if rules_text:
            self.rules_editor.setPlainText(rules_text)
        else:
            self.rules_editor.setPlainText('# Keine stream.rules gefunden')
        self.rules_editor.textChanged.connect(self._mark_changes)

        layout.addWidget(rules_group)
        layout.addStretch()
        scroll.setWidget(content)
        self.tabs.addTab(scroll, 'Expert')

    def _is_clock_interface_commented(self):
        """Check if clock.interface is commented out in the PTP0-Driver block."""
        if not self.config._loaded_path:
            return False
        try:
            with open(self.config._loaded_path) as f:
                lines = f.readlines()
        except Exception:
            return False
        in_ptp_block = False
        for line in lines:
            stripped = line.strip()
            if '{ factory = spa-node-factory' in stripped or ' factory = ' in stripped:
                in_ptp_block = True
                continue
            if in_ptp_block:
                if stripped.startswith('}'):
                    break
                if 'clock.interface' in stripped:
                    return stripped.startswith('#')
        return False

    # ── Actions ─────────────────────────────────────────────────

    def _on_apply(self):
        try:
            # Collect all widget values
            for key, pw in self.widgets.items():
                pdef = pw.defn
                try:
                    value = pw.get_value()
                except Exception:
                    continue
                if pdef.module == 'context.objects':
                    keys = ('context.objects', 0) + pdef.path
                else:
                    keys = ('context.modules', pdef.module) + pdef.path
                
                self.config.set(value, *keys)

            # Handle system clock checkbox
            if self.system_clock_cb:
                use_system = self.system_clock_cb.isChecked()
                if use_system:
                    # Comment out clock.interface in raw text
                    lines = self.config._raw_lines
                    for idx, line in enumerate(lines):
                        if 'clock.interface' in line and not line.strip().startswith('#'):
                            lines[idx] = '# ' + line
                            break
                    self.config._modified = True
                else:
                    # Uncomment clock.interface
                    lines = self.config._raw_lines
                    for idx, line in enumerate(lines):
                        stripped = line.strip()
                        if stripped.startswith('#') and 'clock.interface' in stripped:
                            lines[idx] = stripped.lstrip('# ')
                            break

            # Collect sink tab values
            for tab in self.rtp_sink_tabs:
                vals = tab.collect_values()
                for key, val in vals.items():
                    pdef = PARAM_MAP.get(key)
                    if pdef and pdef.module == 'libpipewire-module-rtp-sink':
                        keys = ('context.modules', tab.sink_index) + pdef.path
                        self.config.set(val, *keys)

            # Save stream.rules raw editor
            if hasattr(self, 'rules_editor'):
                rules_text = self.rules_editor.toPlainText().strip()
                if rules_text and not rules_text.startswith('#'):
                    self.config.set_raw_block(
                        rules_text,
                        'context.modules', 'libpipewire-module-rtp-sap',
                        'args', 'stream.rules'
                    )

            self.config.save()
            QMessageBox.information(self, 'Erfolg', 'Config gespeichert.')
            self._has_changes = False
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, 'Fehler', f'Config konnte nicht gespeichert werden:\n{e}')

    def _on_cancel(self):
        if self._has_changes:
            reply = QMessageBox.question(
                self, 'Änderungen verwerfen?',
                'Es gibt ungespeicherte Änderungen. Trotzdem schliessen?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.reject()

    def _on_reset(self):
        reply = QMessageBox.warning(
            self, 'Config zurücksetzen',
            'Bist du sicher? Die aktuelle Config wird durch die\n'
            'Default-Config von /usr/share/pipewire/pipewire-aes67.conf ersetzt.\n'
            'Ein Backup wird als .bak gespeichert.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.config.reset_to_default()
            self.config.load(self.config.get_loaded_path())
            QMessageBox.information(self, 'Zurückgesetzt',
                                    'Config auf Default zurückgesetzt.')
            self._rebuild_sink_tabs()
            self._reload_all_widgets()
        except Exception as e:
            QMessageBox.critical(self, 'Fehler', f'Reset fehlgeschlagen:\n{e}')

    def _reload_all_widgets(self):
        """Reload all widget values from config."""
        for key, pw in self.widgets.items():
            pdef = pw.defn
            if pdef.module == 'context.objects':
                keys = ('context.objects', 0) + pdef.path
            elif pdef.module:
                keys = ('context.modules', pdef.module) + pdef.path
            else:
                continue
            val = self.config.get(*keys)
            if val is not None:
                pw.set_value(val)
        self._mark_changes()

    def _mark_changes(self):
        self._has_changes = True

    def _on_add_sink(self):
        idx = self.config.add_rtp_sink()
        if idx >= 0:
            self._rebuild_sink_tabs()
            self._mark_changes()

    def _on_remove_sink(self):
        current = self.sink_tab_widget.currentIndex()
        if current < 0 or current >= len(self.rtp_sink_tabs):
            return
        reply = QMessageBox.question(
            self, 'Sink entfernen',
            'Diesen Sink wirklich entfernen?\n'
            'Die Konfiguration wird gelöscht.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        modules = self.config._data.get('context.modules', [])
        sink_indices = [i for i, m in enumerate(modules)
                        if isinstance(m, dict) and m.get('name') == 'libpipewire-module-rtp-sink']
        if current < len(sink_indices):
            mod_idx = sink_indices[current]
            if self.config.remove_rtp_sink(mod_idx):
                self._rebuild_sink_tabs()
                self._mark_changes()
