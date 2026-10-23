"""Selected red UI reference, semantic tokens and persistent live themes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from string import Template

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class ThemeMode(str, Enum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class Tokens:
    background: str
    surface: str
    border: str
    text: str
    secondary: str
    accent: str
    accent_hover: str
    accent_soft: str
    success: str
    warning: str
    inactive: str
    input: str
    input_border: str
    table_header: str
    table_alt: str
    disabled_bg: str
    disabled_fg: str
    tooltip: str
    tooltip_fg: str


LIGHT = Tokens(
    "#F6F8FA", "#FFFFFF", "#E2E7EC", "#17202B", "#6B7888",
    "#C91026", "#A70C21", "#FFF0F2", "#108D44", "#CC941B", "#929EAA",
    "#FFFFFF", "#D9E1E8", "#F3F6F8", "#FAFBFD", "#F4F5F7", "#8794A3",
    "#17202B", "#FFFFFF",
)
DARK = Tokens(
    "#151A21", "#232A33", "#394451", "#F2F5F8", "#B9C5D2",
    "#E3334B", "#F04F64", "#412934", "#47CE81", "#E3BA5D", "#A8B4C1",
    "#2A333D", "#536071", "#303945", "#28313A", "#303945", "#A9B6C6",
    "#EFF3F7", "#151A21",
)

# Compatibility with existing table code; runtime table status colors update
# explicitly on theme switches through the ThemeManager palette.
RED, GREEN, GRAY, MUTED = LIGHT.accent, LIGHT.success, LIGHT.inactive, LIGHT.secondary

_QSS = Template("""
* { font-family: "Noto Sans", "DejaVu Sans", sans-serif; font-size: 12px; color: $text; }
QMainWindow, QWidget#appRoot, QWidget#pageCanvas,
QWidget#pageViewport, QWidget#contentHost, QStackedWidget, QScrollArea,
QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
    background-color: $background;
}
QScrollArea { border: 0; }
QFrame#topBar, QFrame#sidebar { background-color: $surface; border: 0; }
QFrame#topBar { border-bottom: 1px solid $border; }
QFrame#sidebar { border-right: 1px solid $border; }
QLabel { background: transparent; }
QLabel#brandTitle { font-size: 16px; font-weight: 800; }
QLabel#brandSub, QLabel#pageSubtitle, QLabel#secondary,
QLabel#metricLabel { color: $secondary; }
QLabel#pageTitle { font-size: 20px; font-weight: 800; color: $text; }
QLabel#sectionTitle { font-size: 14px; font-weight: 700; }
QLabel#metricNumber { font-size: 23px; font-weight: 800; }
QLabel#metricIcon { color: $accent; font-size: 18px; font-weight: 800; }
QLabel#metricDetail { color: $secondary; font-size: 11px; }
QLabel#metricDetailSuccess { color: $success; font-size: 11px; }
QLabel#brandIcon { color: $accent; font-size: 29px; font-weight: 800; }
QLabel#demoLabel { color: $accent; font-weight: 750; }
QFrame#card, QFrame#panel {
    background-color: $surface; border: 1px solid $border; border-radius: 9px;
}
QPushButton {
    background-color: $surface; color: $text; border: 1px solid $input_border;
    border-radius: 7px; padding: 8px 11px; font-weight: 600; min-height: 19px;
}
QPushButton:hover { background-color: $accent_soft; border-color: $accent; }
QPushButton:disabled {
    background-color: $disabled_bg; color: $disabled_fg; border-color: $border;
}
QPushButton#primary { background-color: $accent; border-color: $accent; color: white; }
QPushButton#primary:hover { background-color: $accent_hover; }
QPushButton#outlineRed { background-color: $accent_soft; color: $accent; border-color: $accent; }
QPushButton#iconAction { padding: 4px 5px; min-height: 18px; font-size: 16px; color: $accent; }
QPushButton#iconAction:disabled { color: $disabled_fg; }
QPushButton#dangerOutline {
    color: $text; border: 1px solid $border;
    border-radius: 8px; background-color: $surface;
}
QPushButton#dangerOutline:hover { border-color: $accent; color: $accent; }
QPushButton#profileToggle, QPushButton#profileEdit,
QPushButton#profileExport, QPushButton#profileDelete {
    padding: 3px 4px; min-height: 20px; min-width: 0px;
    border-radius: 7px; text-align: center;
    font-size: 12px; font-weight: 650;
}
QPushButton#profileDelete:hover {
    background-color: $accent_soft; border-color: $accent;
}
QPushButton#profileToggle:disabled, QPushButton#profileEdit:disabled,
QPushButton#profileExport:disabled, QPushButton#profileDelete:disabled {
    color: $disabled_fg; border-color: $border; background-color: $disabled_bg;
}
QLabel#settingLabel { color: $text; font-size: 12px; }
QPushButton#nav {
    text-align: left; background-color: transparent; border: 0;
    padding: 9px 13px; min-height: 24px; font-weight: 600;
}
QPushButton#nav:hover { background-color: $accent_soft; }
QPushButton#nav:checked { background-color: $accent; color: white; }
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {
    background-color: $input; color: $text; border: 1px solid $input_border;
    border-radius: 9px; padding: 9px 11px; min-height: 22px;
    selection-background-color: $accent; selection-color: white;
}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover { border-color: $secondary; }
QLineEdit[readOnly="true"] { background-color: $table_alt; color: $secondary; }
/* The dropdown chevron is painted by CleanComboBox, independent of GTK.
   Numeric inputs use a validated QLineEdit because Qt's native spinbox
   subcontrol painting made zero-state labels invisible on GNOME/Wayland. */
QComboBox#cleanCombo { padding-right: 33px; }
QComboBox#cleanCombo::drop-down {
    subcontrol-origin: padding; subcontrol-position: top right;
    border: none; width: 29px; background: transparent;
}
QComboBox#cleanCombo::down-arrow { image: none; width: 0px; height: 0px; }
QPushButton#inlineAction {
    border: 1px solid $input_border; border-radius: 8px;
    background-color: $surface; color: $text;
    padding: 8px 10px; min-height: 20px;
}
QPushButton#inlineAction:hover {
    background-color: $accent_soft; border-color: $accent;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: $accent; }
QComboBox QAbstractItemView {
    background-color: $surface; color: $text;
    selection-background-color: $accent_soft; selection-color: $text;
}
QTableWidget {
    background-color: $surface; border: 1px solid $border;
    border-radius: 8px; gridline-color: $border;
    alternate-background-color: $table_alt;
    selection-background-color: $accent_soft; selection-color: $text;
}
QHeaderView::section {
    background-color: $table_header; color: $secondary; border: 0;
    border-bottom: 1px solid $border; padding: 9px 6px; font-weight: 700;
}
QTableWidget::item { padding: 5px; }
QCheckBox { background: transparent; spacing: 8px; }
QCheckBox:disabled { color: $disabled_fg; }
QCheckBox::indicator { width: 16px; height: 16px; }
QCheckBox::indicator:unchecked {
    border: 1px solid $input_border; background: $input; border-radius: 4px;
}
QCheckBox::indicator:checked {
    border: 1px solid $accent; background: $accent; border-radius: 4px;
}
QStatusBar { background-color: $surface; border-top: 1px solid $border; color: $secondary; }
QMenu { background-color: $surface; color: $text; border: 1px solid $border; }
QMenu::item { padding: 8px 17px; }
QMenu::item:selected { background-color: $accent_soft; color: $text; }
QToolTip { background-color: $tooltip; color: $tooltip_fg; border: 1px solid $border; }
QScrollBar:vertical { background: $background; width: 8px; }
QScrollBar::handle:vertical { background: $border; border-radius: 4px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
""")


def stylesheet(tokens: Tokens) -> str:
    return _QSS.substitute(vars(tokens))


def parse_mode(value: object) -> ThemeMode:
    try:
        return ThemeMode(str(value))
    except ValueError:
        return ThemeMode.SYSTEM


def effective_mode(mode: ThemeMode, system_dark: bool) -> ThemeMode:
    return (ThemeMode.DARK if system_dark else ThemeMode.LIGHT) if mode == ThemeMode.SYSTEM else mode


def system_dark(app: QApplication, original: QPalette | None = None) -> bool:
    scheme = app.styleHints().colorScheme()
    if scheme == Qt.ColorScheme.Dark:
        return True
    if scheme == Qt.ColorScheme.Light:
        return False
    # Falling back to the *original* palette prevents a previously selected
    # forced dark theme from being mistaken for the OS theme.
    return (original or app.palette()).color(QPalette.ColorRole.Window).lightness() < 128


class ThemeManager(QObject):
    changed = Signal(str)

    def __init__(self, app: QApplication, settings: QSettings, parent: QObject | None = None):
        super().__init__(parent)
        self.app = app
        self.settings = settings
        self.mode = parse_mode(settings.value("theme_mode", "system"))
        self._original_palette = QPalette(app.palette())
        self.effective = ThemeMode.LIGHT
        self.tokens = LIGHT
        app.styleHints().colorSchemeChanged.connect(self._system_changed)
        self.apply()

    def _system_changed(self, _scheme: Qt.ColorScheme):
        if self.mode == ThemeMode.SYSTEM:
            self.apply()

    def set_mode(self, mode: str | ThemeMode):
        self.mode = parse_mode(mode.value if isinstance(mode, ThemeMode) else mode)
        self.settings.setValue("theme_mode", self.mode.value)
        self.apply()

    def apply(self):
        self.effective = effective_mode(self.mode, system_dark(self.app, self._original_palette))
        self.tokens = DARK if self.effective == ThemeMode.DARK else LIGHT
        t = self.tokens
        palette = QPalette(self._original_palette)
        for role, color in (
            (QPalette.ColorRole.Window, t.background),
            (QPalette.ColorRole.Base, t.input),
            (QPalette.ColorRole.AlternateBase, t.table_alt),
            (QPalette.ColorRole.WindowText, t.text),
            (QPalette.ColorRole.Text, t.text),
            # Numeric zero labels are placeholders, not spinbox-rendered text.
            (QPalette.ColorRole.PlaceholderText, t.secondary),
            (QPalette.ColorRole.ButtonText, t.text),
            (QPalette.ColorRole.Button, t.surface),
            (QPalette.ColorRole.Highlight, t.accent),
            (QPalette.ColorRole.HighlightedText, "#FFFFFF"),
        ):
            palette.setColor(role, QColor(color))
        self.app.setPalette(palette)
        self.app.setStyleSheet(stylesheet(t))
        self.changed.emit(self.effective.value)
