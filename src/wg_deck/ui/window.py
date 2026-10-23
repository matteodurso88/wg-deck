"""WG Deck: four-page desktop UI with embedded Profiles editor.

Demo data are clearly marked. Live configuration and tunnel actions require
explicit Polkit authentication through the root-owned helper.
"""

from __future__ import annotations

import time
from datetime import datetime
from dataclasses import replace
import time
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSettings, Qt, QThreadPool, QTimer, Signal, Slot, QSize, QUrl
from PySide6.QtGui import QColor, QPixmap, QDesktopServices
from PySide6.QtWidgets import (
    QBoxLayout, QCheckBox, QComboBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QInputDialog, QPushButton,
    QScrollArea, QSpinBox, QStackedWidget, QStatusBar, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView, QSystemTrayIcon,
    QApplication, QGraphicsOpacityEffect,
)

from .. import __version__
from ..core.autostart import AutostartError, is_enabled as autostart_enabled, set_enabled as set_autostart
from ..core.demo import demo_inventory
from ..core.discovery import Inventory, discover
from ..core.models import TunnelState
from ..qt_icon import make_app_icon
from .theme import LIGHT, ThemeManager, ThemeMode
from .icons import vector_icon
from .widgets import NumericField, CleanComboBox
from .branding import matt88_logo_pixmap, wg_deck_logo_pixmap
from ..core.privileged import (available as helper_available, connection_available,
    execute as helper_execute, read_available, read_bundle, install_bundle,
    list_system_profiles, read_profile)
from ..core.system_profiles import read_native_names
from ..core.traffic import read_native_traffic

NAV = ("Dashboard", "Profiles", "Diagnostics", "Settings")


def named_label(value: str, style: str = "secondary") -> QLabel:
    label = QLabel(value)
    label.setObjectName(style)
    label.setWordWrap(True)
    return label


class BrandLink(QLabel):
    """A branded link with an explicit user-click-only external action."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("Visit matt88.it")
        self.setAccessibleName("Official matt88.it logo — visit website")
        self.setAccessibleDescription("Open matt88.it in your web browser")

    def _open_site(self):
        QDesktopServices.openUrl(QUrl("https://matt88.it"))

    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(event.position().toPoint())):
            self._open_site()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._open_site()
            event.accept()
            return
        super().keyPressEvent(event)


def make_panel() -> tuple[QFrame, QVBoxLayout]:
    panel = QFrame()
    panel.setObjectName("card")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(17, 16, 17, 16)
    layout.setSpacing(10)
    return panel, layout


def page_heading(title: str, subtitle: str, action: QWidget | None = None) -> QHBoxLayout:
    outer = QHBoxLayout()
    text = QVBoxLayout()
    text.setSpacing(4)
    text.addWidget(named_label(title, "pageTitle"))
    text.addWidget(named_label(subtitle, "pageSubtitle"))
    outer.addLayout(text, 1)
    if action:
        outer.addWidget(action, 0, Qt.AlignmentFlag.AlignRight)
    return outer


def action_button(text: str, kind: str = "", enabled: bool = True) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(kind)
    button.setEnabled(enabled)
    if not enabled:
        button.setToolTip("Available after privileged helper and security tests")
    return button


def metric_card(title: str, symbol: str = "◉") -> tuple[QFrame, QLabel, QLabel, QLabel]:
    frame, layout = make_panel()
    layout.setSpacing(3)
    headline = QHBoxLayout()
    marker = named_label(symbol, "metricIcon")
    headline.addWidget(marker)
    headline.addStretch()
    value = named_label("—", "metricNumber")
    headline.addWidget(value)
    layout.addLayout(headline)
    caption = named_label(title, "metricLabel")
    detail = named_label("", "metricDetail")
    layout.addWidget(caption)
    layout.addWidget(detail)
    return frame, value, caption, detail


def safe_handshake(stamp: int | None) -> str:
    if not stamp:
        return "Never / unavailable"
    delta = max(0, int(time.time()) - stamp)
    if delta < 60:
        return f"{delta}s ago"
    if delta < 3600:
        return f"{delta // 60}m ago"
    return f"{delta // 3600}h ago"


def format_bytes(value: int | float | None) -> str:
    if value is None:
        return "Unavailable"
    quantity = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if quantity < 1024 or unit == "TiB":
            return f"{quantity:.0f} {unit}" if unit == "B" else f"{quantity:.1f} {unit}"
        quantity /= 1024
    return "—"


class InventorySignals(QObject):
    finished = Signal(object)


class InventoryWorker(QRunnable):
    """Every scan uses native system state. No cached application catalogue."""

    def __init__(self):
        super().__init__()
        self.signals = InventorySignals()

    @Slot()
    def run(self) -> None:
        try:
            names = read_native_names()
            if names is None:
                snapshot = discover(directories=(Path("/etc/wireguard"),))
                snapshot = Inventory(
                    snapshot.profiles,
                    snapshot.warnings + (
                        "Native system inventory is unavailable; reinstall the root-owned helper to show inactive profiles.",
                    ),
                    snapshot.wg_version,
                    snapshot.wireguard_tools,
                )
            else:
                snapshot = discover(directories=(), extra_names=names)
                allowed = set(names)
                traffic = read_native_traffic()
                profiles = []
                for profile in snapshot.profiles:
                    if profile.name not in allowed:
                        continue
                    row = traffic.get(profile.name) if traffic is not None else None
                    if row is not None:
                        profiles.append(replace(
                            profile,
                            state=TunnelState.UP if row.is_up else TunnelState.DOWN,
                            rx_bytes=row.rx_bytes, tx_bytes=row.tx_bytes,
                            last_handshake=row.latest_handshake,
                        ))
                    elif profile.state == TunnelState.UP:
                        # ip link can show an interface UP even when unprivileged
                        # wg cannot read its transfer counters. Never invent 0 B.
                        profiles.append(replace(profile, rx_bytes=None, tx_bytes=None))
                    else:
                        profiles.append(profile)
                warnings = tuple(
                    w for w in snapshot.warnings
                    if "No visible profiles" not in w
                    and not (traffic is not None and "wg interface inventory is unavailable" in w)
                )
                if names and traffic is None:
                    warnings += ("Traffic telemetry is unavailable or stale: install/enable the root-owned metrics timer.",)
                elif names and any(p.state == TunnelState.UP and p.rx_bytes is None for p in profiles):
                    warnings += ("At least one active interface has unavailable transfer counters.",)
                snapshot = Inventory(
                    tuple(profiles),
                    warnings if names else ("No native WireGuard profiles installed.",),
                    snapshot.wg_version, snapshot.wireguard_tools,
                )
        except Exception:
            snapshot = Inventory((), ("System inventory temporarily unavailable.",))
        self.signals.finished.emit(snapshot)


class OperationSignals(QObject):
    finished = Signal(str, str, object)


class OperationWorker(QRunnable):
    def __init__(self, action: str, name: str, config: str | None = None, revision: str | None = None):
        super().__init__()
        self.action = action
        self.name = name
        self.config = config
        self.revision = revision
        self.signals = OperationSignals()

    @Slot()
    def run(self):
        result = helper_execute(self.action, self.name, self.config, self.revision)
        self.signals.finished.emit(self.action, self.name, result)


class SystemSignals(QObject):
    finished = Signal(str, object)


class SystemWorker(QRunnable):
    def __init__(self, action: str, name: str = ""):
        super().__init__()
        self.action = action
        self.name = name
        self.signals = SystemSignals()

    @Slot()
    def run(self):
        result = list_system_profiles() if self.action == "list" else read_profile(self.name)
        self.signals.finished.emit(self.action, result)


class BundleWorker(QRunnable):
    """One root-authorized system action, no configuration details in logs."""

    def __init__(self, action: str, data: bytes = b""):
        super().__init__()
        self.action = action
        self.data = data
        self.signals = SystemSignals()

    @Slot()
    def run(self):
        result = read_bundle() if self.action == "export" else install_bundle(self.data)
        self.signals.finished.emit(self.action, result)


class ProfileTable(QTableWidget):
    ACTION_COLUMN_WIDTH = 248
    ACTION_ROW_HEIGHT = 54
    requested = Signal(str, str)
    edit_requested = Signal(str)
    export_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, owner=None):
        super().__init__(0, 6, owner)
        self.setHorizontalHeaderLabels(
            ("Name", "Status", "Endpoint", "RX / TX", "Last Handshake", "Actions")
        )
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        # ResizeToContents inspects the *empty* last-cell QTableWidgetItem,
        # not the two embedded QPushButtons: it cut off the Actions column.
        self.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(5, self.ACTION_COLUMN_WIDTH)
        self.setShowGrid(False)
        self.setMinimumHeight(150)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _request_toggle(self):
        button = self.sender()
        if button is not None:
            self.requested.emit(button.property("wgmOperation"), button.property("wgmProfile"))

    def _request_edit(self):
        button = self.sender()
        if button is not None:
            self.edit_requested.emit(button.property("wgmProfile"))

    def _request_export(self):
        button = self.sender()
        if button is not None:
            self.export_requested.emit(button.property("wgmProfile"))

    def _request_delete(self):
        button = self.sender()
        if button is not None:
            self.delete_requested.emit(button.property("wgmProfile"))

    def _actions_for_row(self, row: int):
        """Reuse four controls per row and avoid accumulated stale Qt widgets."""
        widget = self.cellWidget(row, 5)
        if widget is not None:
            return widget
        widget = QWidget(self)
        widget.setObjectName("profileRowActions")
        buttons = QHBoxLayout(widget)
        buttons.setContentsMargins(6, 7, 6, 7)
        buttons.setSpacing(5)
        buttons.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toggle = action_button("Connect", "profileToggle", enabled=False)
        toggle.setAccessibleName("Connect or disconnect WireGuard profile")
        toggle.setToolTip("Connect or disconnect this WireGuard profile")
        toggle.setFixedSize(106, 36)
        toggle.setIconSize(QSize(16, 16))
        toggle.clicked.connect(self._request_toggle)
        buttons.addWidget(toggle)
        edit = action_button("", "profileEdit")
        edit.setAccessibleName("Edit WireGuard profile")
        edit.setToolTip("Edit this profile (Polkit authorization)")
        edit.setFixedSize(32, 36)
        edit.setIconSize(QSize(16, 16))
        edit.clicked.connect(self._request_edit)
        buttons.addWidget(edit)
        export = action_button("", "profileExport", enabled=False)
        export.setAccessibleName("Export WireGuard profile")
        export.setToolTip("Export this .conf as a protected 0600 file")
        export.setFixedSize(32, 36)
        export.setIconSize(QSize(16, 16))
        export.clicked.connect(self._request_export)
        buttons.addWidget(export)
        delete = action_button("", "profileDelete", enabled=False)
        delete.setAccessibleName("Delete WireGuard profile")
        delete.setToolTip("Delete this disconnected native profile after a protected backup")
        delete.setFixedSize(32, 36)
        delete.setIconSize(QSize(16, 16))
        delete.clicked.connect(self._request_delete)
        buttons.addWidget(delete)
        self.setCellWidget(row, 5, widget)
        return widget

    def populate(self, records, query: str = "", controls_enabled: bool = False,
                 manage_enabled: bool = False):
        query = query.casefold().strip()
        selected = [p for p in records if query in p.name.casefold()]
        self.visible_profiles = selected
        # Removed rows must stop painting immediately, even if Qt has not yet
        # processed deferred widget deletion (important for offscreen capture).
        for row in range(len(selected), self.rowCount()):
            previous = self.cellWidget(row, 5)
            if previous is not None:
                previous.hide()
        self.setRowCount(len(selected))
        for row, profile in enumerate(selected):
            active = profile.state == TunnelState.UP
            unknown = profile.state == TunnelState.UNKNOWN
            status = "●  Interface UP" if active else ("○  Unknown" if unknown else "●  Interface down")
            values = (
                profile.name,
                status,
                profile.endpoint or "—",
                f"{format_bytes(profile.rx_bytes)} / {format_bytes(profile.tx_bytes)}",
                safe_handshake(profile.last_handshake),
            )
            for column, value in enumerate(values):
                cell = self.item(row, column)
                if cell is None:
                    cell = QTableWidgetItem()
                    cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    self.setItem(row, column, cell)
                cell.setText(value)
                if column == 1:
                    tokens = getattr(getattr(self.window(), "theme", None), "tokens", LIGHT)
                    cell.setForeground(QColor(tokens.success if active else tokens.inactive))
            actions = self._actions_for_row(row)
            toggle = actions.findChild(QPushButton, "profileToggle")
            edit = actions.findChild(QPushButton, "profileEdit")
            export = actions.findChild(QPushButton, "profileExport")
            delete = actions.findChild(QPushButton, "profileDelete")
            allowed = controls_enabled and not unknown
            toggle.setText("Disconnect" if active else "Connect")
            tokens = getattr(getattr(self.window(), "theme", None), "tokens", LIGHT)
            toggle.setIcon(vector_icon("disconnect" if active else "connect", tokens.secondary, 16))
            edit.setIcon(vector_icon("edit", tokens.secondary, 16))
            export.setIcon(vector_icon("export", tokens.secondary, 16))
            delete.setIcon(vector_icon("trash", tokens.accent, 16))
            export.setEnabled(manage_enabled)
            delete.setEnabled(manage_enabled and not active and not unknown)
            toggle.setEnabled(allowed)
            toggle.setToolTip(
                "Connect or disconnect this WireGuard profile" if allowed
                else "Install helper and load interface state first"
            )
            toggle.setProperty("wgmOperation", "down" if active else "up")
            toggle.setProperty("wgmProfile", profile.name)
            edit.setProperty("wgmProfile", profile.name)
            export.setProperty("wgmProfile", profile.name)
            delete.setProperty("wgmProfile", profile.name)
            self.setRowHeight(row, self.ACTION_ROW_HEIGHT)
        # Avoid a tall empty panel for only one or two native profiles.
        # For large inventories, cap at 11 rows and scroll inside the table.
        rows_visible = min(len(selected), 11)
        table_height = self.horizontalHeader().height() + rows_visible * self.ACTION_ROW_HEIGHT + 10
        self.setFixedHeight(max(150, table_height))


class MainWindow(QMainWindow):
    def __init__(self, *, demo: bool = False):
        super().__init__()
        self.demo = demo
        self.imported_profile = False
        self.import_original = None
        self.import_source_name = None
        self.edit_revision = None
        self.edit_name = None
        self.edit_original = None
        self.peer_states = []
        self.current_peer_index = 0
        self.inventory = Inventory((), ("Loading read-only inventory…",))
        self._refreshing = False
        self._traffic_sample = None
        self.pool = QThreadPool.globalInstance()
        self.setWindowTitle("WG Deck")
        # Prefer a comfortably sized desktop window, but respect the monitor
        # work area (including the GNOME top bar and dock).
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        preferred_width = min(1400, max(940, available.width() - 64)) if available else 1400
        preferred_height = min(920, max(630, available.height() - 90)) if available else 920
        self.setMinimumSize(940, 630)
        self.resize(preferred_width, preferred_height)
        self.setWindowIcon(make_app_icon())
        self.preferences = QSettings("WORKSHOP", "WGQuickManager")
        # QSettings stores preferences only, never identities of VPN profiles.
        self.preferences.remove("known_profiles")
        self.preferences.remove("managed_profiles")
        self.edit_revision = None
        self.edit_name = None
        self.edit_original = None
        self._busy_action = False
        self._quit_requested = False
        self.theme = ThemeManager(QApplication.instance(), self.preferences, self)

        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        vertical = QVBoxLayout(root)
        vertical.setContentsMargins(0, 0, 0, 0)
        vertical.setSpacing(0)

        header = QFrame()
        header.setObjectName("topBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(23, 12, 23, 12)
        brand = QVBoxLayout()
        brand.setSpacing(1)
        self.wgdeck_header_logo = QLabel()
        self.wgdeck_header_logo.setAccessibleName("WG Deck official logo")
        self.wgdeck_header_logo.setFixedSize(184, 38)
        brand.addWidget(self.wgdeck_header_logo)
        brand.addWidget(named_label("Manage WireGuard VPN connections", "brandSub"))
        header_layout.addLayout(brand)
        self._refresh_wgdeck_header_logo(self.theme.effective.value)
        header_layout.addStretch()
        self.demo_label = named_label("DEMO DATA — not connected", "demoLabel")
        self.demo_label.setVisible(demo)
        header_layout.addWidget(self.demo_label)
        vertical.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(0)
        vertical.addLayout(body, 1)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(184)
        self.sidebar_frame = sidebar
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(12, 18, 12, 12)
        nav.setSpacing(5)
        self.nav_buttons = []
        self.pages = QStackedWidget()
        for index, name in enumerate(NAV):
            button = QPushButton(name)
            button.setIcon(vector_icon(name, self.theme.tokens.secondary))
            button.setIconSize(QSize(19, 19))
            button.setObjectName("nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, idx=index: self.go(idx))
            nav.addWidget(button)
            self.nav_buttons.append(button)
        nav.addStretch()
        nav.addWidget(named_label(f"WG Deck v{__version__}", "secondary"))
        self.sidebar_matt88_logo = BrandLink()
        subtle_brand = QGraphicsOpacityEffect(self.sidebar_matt88_logo)
        subtle_brand.setOpacity(0.64)
        self.sidebar_matt88_logo.setGraphicsEffect(subtle_brand)
        self.sidebar_matt88_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(
            self.sidebar_matt88_logo, 0, Qt.AlignmentFlag.AlignHCenter
        )
        self._refresh_matt88_logo(self.theme.effective.value)
        body.addWidget(sidebar)

        holder = QWidget()
        holder.setObjectName("contentHost")
        column = QVBoxLayout(holder)
        column.setContentsMargins(18, 17, 18, 13)
        self.content_column = column
        column.addWidget(self.pages)
        body.addWidget(holder, 1)

        self.build_dashboard()
        self.build_profiles()
        self.build_editor()
        self.build_diagnostics()
        self.build_settings()
        self.theme.changed.connect(self._theme_changed)
        self.go(0)
        self._update_responsive()

        status = QStatusBar()
        self.setStatusBar(status)
        self.statusBar().showMessage(
            "WireGuard profile operations require Polkit authorization."
            if not self.demo and helper_available()
            else "Read-only mode. Install the trusted helper to manage new profiles."
        )
        self.setup_tray()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(10_000)
        self.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # resizeEvent can fire during construction before page layouts exist.
        if all(hasattr(self, name) for name in (
            "editor_split", "metric_cards", "diagnostics_cards", "settings_cards",
            "dashboard_table", "profiles_table",
        )):
            self._update_responsive()

    def _update_responsive(self):
        """Reflow layout using window width; preserve page state and input data."""
        width = self.width()
        compact = width < 1150
        narrow = width < 1020
        state = (compact, narrow)
        if getattr(self, "_responsive_state", None) == state:
            return
        self._responsive_state = state
        self.editor_split.setDirection(
            QBoxLayout.Direction.TopToBottom if compact
            else QBoxLayout.Direction.LeftToRight
        )
        if hasattr(self, "sidebar_frame"):
            self.sidebar_frame.setFixedWidth(160 if narrow else 184)
            if hasattr(self, "sidebar_matt88_logo"):
                self._refresh_matt88_logo(self.theme.effective.value)
        if hasattr(self, "content_column"):
            self.content_column.setContentsMargins(
                12 if compact else 18, 13 if compact else 17,
                12 if compact else 18, 10 if compact else 13,
            )

        metric_cols = 2 if compact else 4
        for index, card in enumerate(self.metric_cards):
            self.metrics_grid.removeWidget(card)
            self.metrics_grid.addWidget(card, index // metric_cols, index % metric_cols)

        diag_cols = 2 if compact else 4
        for index, card in enumerate(self.diagnostics_cards):
            self.diagnostics_grid.removeWidget(card)
            self.diagnostics_grid.addWidget(card, index // diag_cols, index % diag_cols)

        settings_cols = 1 if narrow else 2
        self.settings_grid.setColumnStretch(0, 1)
        self.settings_grid.setColumnStretch(1, 0 if narrow else 1)
        for index, card in enumerate(self.settings_cards):
            self.settings_grid.removeWidget(card)
            self.settings_grid.addWidget(card, index // settings_cols, index % settings_cols)

        # The only stretch column must always be visible: on compact windows
        # Status fills the remaining viewport and pins Actions at the far right.
        # Stretching hidden Endpoint left huge unused space in the table.
        for table in (self.dashboard_table, self.profiles_table):
            header = table.horizontalHeader()
            for col in (2, 3, 4):
                table.setColumnHidden(col, narrow)
            header.setSectionResizeMode(
                1, QHeaderView.ResizeMode.Stretch if narrow
                else QHeaderView.ResizeMode.ResizeToContents
            )
            header.setSectionResizeMode(
                2, QHeaderView.ResizeMode.ResizeToContents if narrow
                else QHeaderView.ResizeMode.Stretch
            )
            # Never let Qt auto-compress action widgets into the header text
            # width: the full-size Connect/Disconnect and Edit must fit.
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(5, ProfileTable.ACTION_COLUMN_WIDTH)
            header.setStretchLastSection(False)
            table.viewport().update()

    def scroll_page(self, content: QWidget) -> None:
        self.pages.addWidget(self._make_scroll(content))

    def _make_scroll(self, content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setObjectName("pageViewport")
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        return scroll

    def new_content(self):
        content = QWidget()
        content.setObjectName("pageCanvas")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(12)
        return content, layout

    def go(self, index: int):
        self.pages.setCurrentIndex(index)
        if index == 1 and hasattr(self, "profiles_stack"):
            self.profiles_stack.setCurrentIndex(0)
        for idx, button in enumerate(self.nav_buttons):
            button.setChecked(idx == index)
            button.setIcon(vector_icon(NAV[idx], "#FFFFFF" if idx == index else self.theme.tokens.secondary))

    def build_dashboard(self):
        content, layout = self.new_content()
        add = action_button("New Profile", "primary")
        add.setIcon(vector_icon("new", "#FFFFFF"))
        add.setProperty("wgmIconName", "new")
        add.clicked.connect(self.new_profile)
        layout.addLayout(page_heading("Overview", "Manage and inspect your WireGuard VPN profiles", add))
        grid = QGridLayout()
        grid.setSpacing(12)
        self.metrics_grid = grid
        self.metric_cards = []
        self.metrics = []
        self.metric_details = []
        for col, (title, symbol) in enumerate((
            ("Total Profiles", "◎"), ("Connected", "●"),
            ("Disconnected", "●"), ("Total Transfer", "▥"),
        )):
            frame, value, _, detail = metric_card(title, symbol)
            if col == 1:
                detail.setObjectName("metricDetailSuccess")
            self.metrics.append(value)
            self.metric_details.append(detail)
            self.metric_cards.append(frame)
            grid.addWidget(frame, 0, col)
        layout.addLayout(grid)

        controls = QHBoxLayout()
        controls.addWidget(named_label("VPN Profiles", "sectionTitle"))
        controls.addStretch()
        self.dashboard_search = QLineEdit()
        self.dashboard_search.setPlaceholderText("Search profiles…")
        self.dashboard_search.setFixedWidth(225)
        self.dashboard_search.textChanged.connect(self.fill_tables)
        controls.addWidget(self.dashboard_search)
        layout.addLayout(controls)

        self.dashboard_table = ProfileTable()
        self.dashboard_table.requested.connect(self.request_operation)
        self.dashboard_table.edit_requested.connect(self.open_existing_profile)
        # Both pages dispatch EXACTLY the same per-profile actions.
        self.dashboard_table.export_requested.connect(self.export_profile)
        self.dashboard_table.delete_requested.connect(self.delete_profile)
        self.dashboard_table.cellDoubleClicked.connect(self.show_profile_details)
        layout.addWidget(self.dashboard_table)
        self.dashboard_note = named_label("", "secondary")
        layout.addWidget(self.dashboard_note)
        layout.addStretch()
        self.scroll_page(content)

    def build_profiles(self):
        content, layout = self.new_content()
        toolbar = QWidget()
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(0, 0, 0, 0)
        add = action_button("New Profile", "primary")
        add.setIcon(vector_icon("new", "#FFFFFF"))
        add.setProperty("wgmIconName", "new")
        add.clicked.connect(self.new_profile)
        bar.addWidget(add)
        imp = action_button("Import")
        imp.setIcon(vector_icon("import", self.theme.tokens.secondary))
        imp.setProperty("wgmIconName", "import")
        imp.setText("Import Backup")
        imp.clicked.connect(self.import_all_profiles)
        bar.addWidget(imp)
        exp = action_button("Export")
        exp.setIcon(vector_icon("export", self.theme.tokens.secondary))
        exp.setProperty("wgmIconName", "export")
        exp.setText("Export All")
        exp.clicked.connect(self.export_all_profiles)
        bar.addWidget(exp)
        layout.addLayout(page_heading(
            "Profiles", "Native WireGuard configurations from /etc/wireguard"
        ))
        layout.addWidget(toolbar)
        self.profiles_search = QLineEdit()
        self.profiles_search.setPlaceholderText("Filter visible profiles…")
        self.profiles_search.textChanged.connect(self.fill_tables)
        layout.addWidget(self.profiles_search)
        self.profiles_table = ProfileTable()
        self.profiles_table.requested.connect(self.request_operation)
        self.profiles_table.edit_requested.connect(self.open_existing_profile)
        self.profiles_table.export_requested.connect(self.export_profile)
        self.profiles_table.delete_requested.connect(self.delete_profile)
        self.profiles_table.cellDoubleClicked.connect(self.edit_selected_profile)
        layout.addWidget(self.profiles_table)
        layout.addWidget(named_label(
            "Import/Export Backup manages ALL native .conf files in one ZIP. "
            "Use the icons in each row to export, edit or delete a single profile.",
            "secondary"
        ))
        layout.addStretch()
        self.profiles_stack = QStackedWidget()
        self.profiles_stack.addWidget(self._make_scroll(content))
        self.pages.addWidget(self.profiles_stack)

    def build_editor(self):
        content, layout = self.new_content()
        cancel = action_button("Back to Profiles")
        cancel.setIcon(vector_icon("back", self.theme.tokens.secondary))
        cancel.setProperty("wgmIconName", "back")
        cancel.clicked.connect(self.back_to_profiles)
        layout.addLayout(page_heading("Profile configuration", "Edit WireGuard interface and peers", cancel))
        name_frame, name_layout = make_panel()
        name_layout.addWidget(named_label("Profile Name", "sectionTitle"))
        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("e.g. office-vpn")
        name_layout.addWidget(self.profile_name)
        layout.addWidget(name_frame)

        split = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        split.setSpacing(14)
        self.editor_split = split
        interface, left = make_panel()
        left.addWidget(named_label("⚙  Interface", "sectionTitle"))
        interface_fields = QFormLayout()
        interface_fields.setHorizontalSpacing(14)
        interface_fields.setVerticalSpacing(10)
        interface_fields.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        interface_fields.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.address = QLineEdit()
        self.address.setPlaceholderText("Required — e.g. 198.18.77.2/32")
        self.address.setToolTip("Required interface address with prefix, for example 198.18.77.2/32")
        self.listen_port = NumericField()
        self.listen_port.setRange(0, 65535)
        self.listen_port.setSpecialValueText("Automatic")
        self.private_key = QLineEdit()
        self.private_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.private_key.setPlaceholderText("Required — generate a new keypair")
        self.dns = QLineEdit()
        self.dns.setPlaceholderText("1.1.1.1, 1.0.0.1")
        self.mtu = NumericField()
        self.mtu.setRange(0, 9000)
        self.mtu.setSpecialValueText("Automatic")
        interface_fields.addRow("Address *", self.address)
        interface_fields.addRow("Listen Port", self.listen_port)
        self.generate_keys = action_button("Generate", "inlineAction")
        self.generate_keys.setToolTip("Generate a local private/public WireGuard keypair")
        self.generate_keys.setAccessibleName("Generate new WireGuard keypair")
        self.generate_keys.setIcon(vector_icon("key", self.theme.tokens.secondary))
        self.generate_keys.setProperty("wgmIconName", "key")
        self.generate_keys.clicked.connect(self.generate_interface_keys)
        secret_line = QWidget()
        secret_row = QHBoxLayout(secret_line)
        secret_row.setContentsMargins(0, 0, 0, 0)
        secret_row.setSpacing(7)
        secret_row.addWidget(self.private_key, 1)
        secret_row.addWidget(self.generate_keys)
        interface_fields.addRow("Private Key *", secret_line)
        self.interface_public_key = QLineEdit()
        self.interface_public_key.setReadOnly(True)
        self.interface_public_key.setPlaceholderText("Derived public key")
        self.interface_public_key.setToolTip("Safe to share with the remote WireGuard peer")
        self.copy_public_key_button = action_button("Copy", "inlineAction")
        self.copy_public_key_button.setToolTip("Copy only the public key")
        self.copy_public_key_button.setAccessibleName("Copy local public key")
        self.copy_public_key_button.setIcon(vector_icon("copy", self.theme.tokens.secondary))
        self.copy_public_key_button.setProperty("wgmIconName", "copy")
        self.copy_public_key_button.clicked.connect(self.copy_interface_public_key)
        self.copy_public_key_button.setEnabled(False)
        self.interface_public_key.textChanged.connect(
            lambda value: self.copy_public_key_button.setEnabled(bool(value))
        )
        public_line = QWidget()
        public_row = QHBoxLayout(public_line)
        public_row.setContentsMargins(0, 0, 0, 0)
        public_row.setSpacing(7)
        public_row.addWidget(self.interface_public_key, 1)
        public_row.addWidget(self.copy_public_key_button)
        interface_fields.addRow("Local Public Key", public_line)
        interface_fields.addRow("DNS", self.dns)
        interface_fields.addRow("MTU", self.mtu)
        left.addLayout(interface_fields)
        left.addStretch()
        split.addWidget(interface, 1)

        peer, right = make_panel()
        right.addWidget(named_label("♟  Peers", "sectionTitle"))
        peer_controls = QHBoxLayout()
        self.peer_selector = CleanComboBox()
        self.peer_selector.addItem("Peer 1")
        peer_controls.addWidget(self.peer_selector, 1)
        self.add_peer_button = action_button("＋ Peer")
        self.add_peer_button.clicked.connect(self.add_peer)
        peer_controls.addWidget(self.add_peer_button)
        self.remove_peer_button = action_button("− Peer", enabled=False)
        self.remove_peer_button.clicked.connect(self.remove_peer)
        peer_controls.addWidget(self.remove_peer_button)
        right.addLayout(peer_controls)
        peer_fields = QFormLayout()
        peer_fields.setHorizontalSpacing(14)
        peer_fields.setVerticalSpacing(10)
        peer_fields.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        peer_fields.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.public_key = QLineEdit()
        self.public_key.setPlaceholderText("Required — remote peer public key")
        self.preshared_key = QLineEdit()
        self.preshared_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.endpoint = QLineEdit()
        self.endpoint.setPlaceholderText("vpn.example.com:51820")
        self.allowed_ips = QLineEdit()
        self.allowed_ips.setPlaceholderText("Required — e.g. 198.18.77.1/32")
        self.allowed_ips.setToolTip("Required route(s) for this peer, with CIDR prefix. An empty field is not a default route.")
        self.keepalive = NumericField()
        self.keepalive.setRange(0, 65535)
        self.keepalive.setSpecialValueText("Disabled")
        self.keepalive.setToolTip("Persistent keepalive in seconds; 0 disables it")
        peer_fields.addRow("Public Key *", self.public_key)
        peer_fields.addRow("Preshared Key", self.preshared_key)
        peer_fields.addRow("Endpoint", self.endpoint)
        peer_fields.addRow("Allowed IPs *", self.allowed_ips)
        peer_fields.addRow("Keepalive (s)", self.keepalive)
        right.addLayout(peer_fields)
        self.peer_states = [self._read_peer()]
        self.peer_selector.currentIndexChanged.connect(self._switch_peer)
        right.addStretch()
        split.addWidget(peer, 1)
        layout.addLayout(split)

        buttons = QHBoxLayout()
        # New/Import/Export live in the Profiles workspace toolbar.
        # Editor footer keeps only actions for the configuration being edited.
        buttons.addStretch()
        self.install_button = action_button("Create Profile", "primary",
                                            enabled=not self.demo and helper_available())
        self.install_button.clicked.connect(self.install_new_profile)
        buttons.addWidget(self.install_button)
        layout.addLayout(buttons)
        self.editor_note = named_label(
            "Create Profile writes a native /etc/wireguard/<name>.conf via Polkit, "
            "without activating the tunnel. Import loads an external draft; "
            "Export of installed profiles lives in the Profiles list.",
            "secondary",
        )
        layout.addWidget(self.editor_note)
        layout.addStretch()
        self.profiles_stack.addWidget(self._make_scroll(content))

    def back_to_profiles(self):
        self.go(1)

    def _show_profile_editor(self):
        self.go(1)
        self.profiles_stack.setCurrentIndex(1)

    def _selected_profile(self) -> str | None:
        index = self.profiles_table.currentRow()
        records = getattr(self.profiles_table, "visible_profiles", [])
        return records[index].name if 0 <= index < len(records) else None

    def edit_selected_profile(self, row: int, _column: int):
        profiles = getattr(self.profiles_table, "visible_profiles", [])
        if 0 <= row < len(profiles):
            self.open_existing_profile(profiles[row].name)

    def load_system_profiles(self):
        if self.demo:
            self.statusBar().showMessage("Demo mode does not read system profiles.")
            return
        self._start_system_read("list")

    def open_existing_profile(self, name: str):
        if self.demo:
            self.statusBar().showMessage("Editing live profiles is unavailable in demo mode.")
            return
        self._start_system_read("read", name)

    def export_all_profiles(self):
        """Create one ZIP containing all native system .conf files."""
        if self.demo:
            QMessageBox.information(self, "Demo", "System backup is unavailable in demo mode.")
            return
        if self._busy_action:
            return
        if not helper_available():
            QMessageBox.warning(self, "Helper unavailable", "Reinstall the trusted helper first.")
            return
        # Export All itself is an explicit intent; avoid stacking a redundant
        # confirmation dialog over Polkit and the file-save chooser.
        # The save dialog warns about private keys and protects the destination.
        self._start_bundle_job("export")

    def import_all_profiles(self):
        """Top-level import supports a native ZIP or the legacy single .conf."""
        from PySide6.QtWidgets import QFileDialog
        from ..core.profile_bundle import preview_bundle, BundleError, MAX_BUNDLE
        selected, _ = QFileDialog.getOpenFileName(
            self, "Import WireGuard native backup", "",
            "WireGuard backup ZIP (*.zip);;Single WireGuard config (*.conf)",
        )
        if not selected:
            return
        if selected.lower().endswith(".conf"):
            self.import_config(selected)
            return
        if not selected.lower().endswith(".zip"):
            QMessageBox.warning(self, "Unsupported backup", "Choose a .zip or .conf file.")
            return
        if self.demo or self._busy_action or not helper_available():
            QMessageBox.warning(self, "Import unavailable", "Exit demo mode and install the trusted helper.")
            return
        try:
            with Path(selected).open("rb") as source:
                data = source.read(MAX_BUNDLE + 1)
            names = preview_bundle(data)
        except (OSError, BundleError):
            QMessageBox.warning(
                self, "Backup import unavailable",
                "The archive is unreadable, too large or contains unsupported native "
                "configuration options. Nothing has been changed."
            )
            return
        if QMessageBox.question(
            self, "Install native WireGuard backup",
            f"Import {len(names)} profiles from this ZIP into /etc/wireguard?\n\n"
            "ONLY new names can be imported. If ANY name already exists, "
            "the entire import is rejected: no overwrite or partial restore.\n"
            "Profiles are NOT connected automatically. Only known safe "
            "wg-quick directives are accepted; executable hooks are refused.\n"
            "Polkit will authorize the installation."
        ) != QMessageBox.StandardButton.Yes:
            return
        self._start_bundle_job("import", data)

    def _start_bundle_job(self, action: str, data: bytes = b""):
        if self._busy_action or self.demo:
            return
        self._busy_action = True
        self.statusBar().showMessage("Archive operation: awaiting Polkit authorization…")
        self.fill_tables()
        worker = BundleWorker(action, data)
        worker.signals.finished.connect(self._finish_bundle_job)
        self._bundle_worker = worker
        self.pool.start(worker)

    def _finish_bundle_job(self, action: str, result):
        self._busy_action = False
        if not result.ok:
            QMessageBox.warning(self, "WireGuard backup", result.message)
        elif action == "export":
            from PySide6.QtWidgets import QFileDialog
            from ..core.profile_bundle import save_bundle, BundleError
            suggested = Path.home() / (
                f"wg-deck-backup-{datetime.now():%Y%m%d-%H%M}.zip"
            )
            destination, _ = QFileDialog.getSaveFileName(
                self, "Export All — PRIVATE KEYS inside ZIP (0600, keep confidential)", str(suggested),
                "WireGuard backup ZIP (*.zip)"
            )
            if destination:
                try:
                    save_bundle(result.data, Path(destination))
                except (BundleError, OSError) as exc:
                    QMessageBox.warning(self, "Backup not saved", str(exc))
                else:
                    self.statusBar().showMessage(
                        "All native profiles exported in one protected ZIP (0600).",
                        9000,
                    )
        else:
            self.statusBar().showMessage(result.message, 9000)
            QTimer.singleShot(1200, self.refresh)
        self.refresh()
        self.fill_tables()

    def export_profile(self, name: str):
        """Export the single native profile associated with this row."""
        if self.demo:
            QMessageBox.information(self, "Demo", "Demo profiles are fictional.")
            return
        if name not in {p.name for p in self.inventory.profiles}:
            QMessageBox.warning(self, "Profile missing", "The native profile is no longer in the inventory.")
            return
        self._start_system_read("export", name)

    def delete_profile(self, name: str):
        """Delete one row, never silently affect any other native profile."""
        if self.demo:
            QMessageBox.information(self, "Demo", "Demo profiles cannot be deleted.")
            return
        if self._busy_action or not helper_available():
            QMessageBox.warning(self, "Helper unavailable", "Reinstall the trusted helper before deleting a profile.")
            return
        selected = next((p for p in self.inventory.profiles if p.name == name), None)
        if selected is None or selected.state != TunnelState.DOWN:
            QMessageBox.warning(
                self, "Disconnect required",
                "Only confirmed disconnected native profiles can be deleted. "
                "Disconnect the VPN and refresh the observed state first."
            )
            return
        reply = QMessageBox.warning(
            self, "Delete native WireGuard profile",
            f"Delete /etc/wireguard/{name}.conf?\n\n"
            "A protected root-only backup is saved before removal. "
            "The active interface will NEVER be disconnected automatically. "
            "Systemd-enabled profiles cannot be deleted until their service "
            "is disabled. This affects a native configuration regardless of "
            "whether it was created in Bash or the GUI.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_operation("delete", name)

    def _start_system_read(self, action: str, name: str = ""):
        if self._busy_action:
            return
        if not helper_available():
            QMessageBox.warning(self, "Helper unavailable", "Reinstall the updated privileged helper first.")
            return
        self._busy_action = True
        self.statusBar().showMessage("Awaiting Polkit authorization…")
        worker = SystemWorker("list" if action == "list" else "read", name)
        worker.signals.finished.connect(
            lambda _type, result, requested=action: self._finish_system_read(requested, result)
        )
        self._system_worker = worker
        self.pool.start(worker)

    def _finish_system_read(self, requested: str, result):
        self._busy_action = False
        if not result.ok:
            QMessageBox.warning(self, "WireGuard", result.message)
            self.fill_tables()
            return
        if requested == "export":
            self._save_authorized_copy(result.name, result.content)
        else:
            self._load_system_editor(result.name, result.content, result.revision)
        self.fill_tables()

    def _save_authorized_copy(self, name: str, content: str):
        from pathlib import Path
        from PySide6.QtWidgets import QFileDialog
        from ..core.profile_copy import export_existing, CopyError
        target, _ = QFileDialog.getSaveFileName(
            self, "Export WireGuard profile", str(Path.home() / f"{name}.conf"),
            "WireGuard (*.conf)"
        )
        if not target:
            return
        try:
            export_existing(name, content, Path(target))
        except (CopyError, OSError) as exc:
            QMessageBox.warning(self, "Export unavailable", str(exc))
            return
        self.statusBar().showMessage("Profile exported as a new local 0600 file.", 7000)

    def _load_system_editor(self, name: str, raw: str, revision: str):
        from ..core.profile_export import parse_supported_profile, ProfileValidationError
        from ..core.config import inspect_config
        # Always preserve the source hash, and never serialize an unsupported
        # directive set using incomplete GUI controls.
        self.new_profile()
        self.edit_name = name
        self.edit_revision = revision
        self.edit_original = raw
        self.profile_name.setText(name)
        self.profile_name.setReadOnly(True)
        try:
            draft = parse_supported_profile(name, raw)
        except ProfileValidationError:
            self.imported_profile = True
            summary = inspect_config(raw)
            self.address.setText(summary.address or "")
            self.private_key.setText(summary.private_key or "")
            self.dns.setText(summary.dns or "")
            self.install_button.setEnabled(False)
            self.add_peer_button.setEnabled(False)
            self.remove_peer_button.setEnabled(False)
            self.editor_note.setText(
                "Read-only preview: unsupported directives or executable hooks. "
                "Export the ORIGINAL file from Profiles; no directives will be lost."
            )
            self._set_editor_locked(True)
            return
        self._set_editor_locked(False)
        self.imported_profile = False
        self.address.setText(draft.address)
        self.private_key.setText(draft.private_key)
        self.dns.setText(draft.dns)
        self.listen_port.setValue(draft.listen_port)
        self.mtu.setValue(draft.mtu)
        self.peer_states = list(draft.peers)
        self.peer_selector.blockSignals(True)
        self.peer_selector.clear()
        for index in range(len(draft.peers)):
            self.peer_selector.addItem(f"Peer {index + 1}")
        self.peer_selector.setCurrentIndex(0)
        self.peer_selector.blockSignals(False)
        self.current_peer_index = -1
        self._switch_peer(0)
        self.install_button.setText("Save Changes")
        self.install_button.setEnabled(helper_available())
        self.editor_note.setText(
            "Editing existing system profile. Save requests Polkit, compares the "
            "original revision and creates a protected backup. Active profiles cannot be overwritten."
        )

    def _set_editor_locked(self, locked: bool):
        for field in (
            self.address, self.private_key, self.dns, self.listen_port,
            self.mtu, self.public_key, self.preshared_key, self.endpoint,
            self.allowed_ips, self.keepalive, self.generate_keys,
            self.add_peer_button, self.remove_peer_button
        ):
            field.setEnabled(not locked)
        self.profile_name.setReadOnly(bool(self.edit_name))
        self.install_button.setEnabled(not locked and helper_available() and not self.demo)

    def generate_interface_keys(self):
        from ..core.keys import generate_keypair, KeyGenerationError
        try:
            private, public = generate_keypair()
        except KeyGenerationError as exc:
            QMessageBox.warning(self, "Key generation unavailable", str(exc))
            return
        self.private_key.setText(private)
        self.interface_public_key.setText(public)
        self.editor_note.setText(
            "A new local WireGuard keypair was generated. The private key is masked; "
            "only the public key should be shared with the VPN server."
        )

    def copy_interface_public_key(self):
        value = self.interface_public_key.text()
        if value:
            QApplication.clipboard().setText(value)
            self.statusBar().showMessage("Public key copied to clipboard.", 5000)

    def _read_peer(self):
        from ..core.profile_export import PeerDraft
        return PeerDraft(
            public_key=self.public_key.text().strip(),
            allowed_ips=self.allowed_ips.text().strip(),
            endpoint=self.endpoint.text().strip(),
            preshared_key=self.preshared_key.text().strip(),
            keepalive=self.keepalive.value(),
        )

    def _store_peer(self):
        if self.peer_states and 0 <= self.current_peer_index < len(self.peer_states):
            self.peer_states[self.current_peer_index] = self._read_peer()

    def _switch_peer(self, index):
        if index < 0 or index >= len(self.peer_states):
            return
        self._store_peer()
        self.current_peer_index = index
        draft = self.peer_states[index]
        self.public_key.setText(draft.public_key)
        self.allowed_ips.setText(draft.allowed_ips)
        self.endpoint.setText(draft.endpoint)
        self.preshared_key.setText(draft.preshared_key)
        self.keepalive.setValue(draft.keepalive)
        self.remove_peer_button.setEnabled(not self.imported_profile and len(self.peer_states) > 1)

    def add_peer(self):
        if self.imported_profile:
            return
        from ..core.profile_export import PeerDraft
        self._store_peer()
        self.peer_states.append(PeerDraft("", ""))
        self.peer_selector.addItem(f"Peer {len(self.peer_states)}")
        self.peer_selector.setCurrentIndex(len(self.peer_states) - 1)

    def remove_peer(self):
        if self.imported_profile or len(self.peer_states) <= 1:
            return
        self._store_peer()
        self.peer_states.pop(self.current_peer_index)
        self.peer_selector.blockSignals(True)
        self.peer_selector.clear()
        for number in range(1, len(self.peer_states) + 1):
            self.peer_selector.addItem(f"Peer {number}")
        target = min(self.current_peer_index, len(self.peer_states) - 1)
        self.peer_selector.setCurrentIndex(target)
        self.peer_selector.blockSignals(False)
        self.current_peer_index = -1  # avoid re-saving the deleted peer into its neighbor
        self._switch_peer(target)

    def _make_draft(self):
        from ..core.profile_export import ProfileDraft
        self._store_peer()
        return ProfileDraft(
            name=self.profile_name.text().strip(),
            address=self.address.text().strip(),
            private_key=self.private_key.text().strip(),
            dns=self.dns.text().strip(),
            listen_port=self.listen_port.value(),
            mtu=self.mtu.value(),
            peers=tuple(self.peer_states),
        )

    def _missing_required_field(self, draft):
        """Return the first blank required input without reading system profiles.

        Placeholders are examples, never saved as real WireGuard settings.
        Every peer has its own required Public Key and Allowed IPs.
        """
        if not draft.name:
            return ("Profile Name", self.profile_name, None)
        if not draft.address:
            return ("Interface Address", self.address, None)
        if not draft.private_key:
            return ("Interface Private Key", self.private_key, None)
        for index, peer in enumerate(draft.peers):
            if not peer.public_key:
                return (f"Peer {index + 1} Public Key", self.public_key, index)
            if not peer.allowed_ips:
                return (f"Peer {index + 1} Allowed IPs", self.allowed_ips, index)
        return None

    def install_new_profile(self):
        from ..core.profile_export import render_new_profile, ProfileValidationError
        if self.demo or self.imported_profile or self._busy_action:
            return
        if not helper_available():
            QMessageBox.warning(self, "Helper missing",
                                "Run: bash scripts/install_helper.sh")
            return
        draft = self._make_draft()
        missing = self._missing_required_field(draft)
        if missing is not None:
            label, field, peer_index = missing
            if peer_index is not None and peer_index != self.peer_selector.currentIndex():
                self.peer_selector.setCurrentIndex(peer_index)
            field.setFocus()
            QMessageBox.warning(
                self, "Required profile field",
                f"{label} is required. The example text in an empty field is "
                "only a placeholder and will not be saved."
            )
            return
        try:
            data = render_new_profile(draft)
            if self.import_original is not None and self.edit_revision is None:
                # Avoid silently dropping comments, line endings or layout
                # from a supported imported configuration.
                from dataclasses import replace as draft_replace
                from ..core.profile_export import parse_supported_profile
                from ..core.profile_rewrite import rewrite_supported_config
                original_draft = parse_supported_profile(
                    self.import_source_name, self.import_original
                )
                if draft_replace(draft, name=self.import_source_name) == original_draft:
                    data = self.import_original
                else:
                    data = rewrite_supported_config(
                        self.import_source_name, self.import_original,
                        draft_replace(draft, name=self.import_source_name),
                    )
        except ProfileValidationError as exc:
            QMessageBox.warning(self, "Invalid profile", str(exc))
            return
        if self.edit_revision:
            from ..core.profile_rewrite import rewrite_supported_config
            try:
                data = rewrite_supported_config(draft.name, self.edit_original, draft)
            except ProfileValidationError as exc:
                QMessageBox.warning(self, "Cannot preserve configuration", str(exc))
                return
            if draft.name != self.edit_name:
                QMessageBox.warning(self, "Profile name", "Existing profile names cannot be changed here.")
                return
            confirm = QMessageBox.question(
                self, "Save system profile changes",
                f"Update {draft.name}.conf?\n"
                "Polkit authorization is required. The previous version will be backed up.\n"
                "The helper refuses to save while the tunnel is active or if the file changed."
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self._start_operation("replace", draft.name, data, self.edit_revision)
            return
        # Explicit Create Profile already expresses intent. The root helper
        # never overwrites and does not auto-connect, so avoid a redundant
        # GUI confirmation on top of the required Polkit authorization.
        self._start_operation("install", draft.name, data)

    def request_operation(self, action: str, name: str):
        if self.demo or self._busy_action:
            return
        if action not in {"up", "down"}:
            return
        # A network change can disrupt routes, DNS and remote access.
        # Confirmation defaults ON but is a user preference; Polkit is always
        # enforced independently by the root-installed connection entrypoint.
        if self.preferences.value("confirm_connection_changes", True, bool):
            consent = QMessageBox.question(
                self, "Confirm WireGuard operation",
                f"{'Connect' if action == 'up' else 'Disconnect'} {name}?\n"
                "This can modify routes and DNS and interrupt active networking.\n"
                "Any PreUp/PostUp/PreDown/PostDown hooks in the root-owned profile "
                "may execute as root. Confirm that you trust this configuration.",
            )
            if consent != QMessageBox.StandardButton.Yes:
                return
        # An unchecked confirmation never bypasses the root-owned Polkit helper.
        self._start_operation(action, name)

    def _start_operation(self, action: str, name: str, config: str | None = None,
                         revision: str | None = None):
        if self._busy_action or self.demo:
            return
        self._busy_action = True
        self.statusBar().showMessage(f"{action.title()} {name}: awaiting authentication…")
        self.fill_tables()
        worker = OperationWorker(action, name, config, revision)
        worker.signals.finished.connect(self._finish_operation)
        self._operation_worker = worker
        self.pool.start(worker)

    def _finish_operation(self, action: str, name: str, result):
        self._busy_action = False
        if result.ok and action == "replace":
            self.edit_revision = None  # force a fresh authorized read before another save
            self.back_to_profiles()
        if result.ok and action == "install":
            self.back_to_profiles()
            # The directory watcher publishes the native file inventory.
            QTimer.singleShot(1500, self.refresh)
        if result.ok and action == "delete":
            # The inventory watcher sees the native file removal.
            QTimer.singleShot(1500, self.refresh)
        self.statusBar().showMessage(result.message, 8000)
        if not result.ok:
            QMessageBox.warning(self, "WireGuard operation failed", result.message)
        self.refresh()
        self.fill_tables()

    def new_profile(self):
        self.imported_profile = False
        self.edit_revision = None
        self.edit_name = None
        self.edit_original = None
        self.profile_name.setReadOnly(False)
        self.install_button.setText("Create Profile")
        self._set_editor_locked(False)
        self.peer_states = []
        self.current_peer_index = 0
        self.peer_selector.blockSignals(True)
        self.peer_selector.clear()
        self.peer_selector.addItem("Peer 1")
        self.peer_selector.blockSignals(False)
        self.remove_peer_button.setEnabled(False)
        self.add_peer_button.setEnabled(True)
        for field in (
            self.profile_name, self.address, self.private_key,
            self.dns, self.interface_public_key, self.public_key, self.preshared_key, self.endpoint,
            self.allowed_ips,
        ):
            field.clear()
        for field in (self.listen_port, self.mtu, self.keepalive):
            field.setValue(0)
        self.peer_states = [self._read_peer()]
        self.install_button.setEnabled(not self.demo and helper_available())
        self.editor_note.setText(
            "New native system profile. Create Profile saves it in /etc/wireguard "
            "after Polkit authorization without connecting or replacing existing VPNs."
        )
        self._show_profile_editor()

    def import_config(self, chosen_path: str | None = None):
        from pathlib import Path
        from PySide6.QtWidgets import QFileDialog
        if chosen_path is None:
            chosen_path, _ = QFileDialog.getOpenFileName(
                self, "Inspect WireGuard configuration", "", "WireGuard profile (*.conf)"
            )
        if not chosen_path:
            return
        path = Path(chosen_path)
        try:
            # Only explicitly user-selected files. 128KiB limit; no logging or raw dump.
            with path.open("rb") as source:
                original_bytes = source.read(128 * 1024 + 1)
            if len(original_bytes) > 128 * 1024:
                raise ValueError("The selected profile is too large.")
            # Bytes first: read_text() translates CRLF on Linux and would
            # silently corrupt an otherwise unchanged native import.
            text = original_bytes.decode("utf-8")
            if "\x00" in text:
                raise ValueError("Binary profile content is not supported.")
            from ..core.config import inspect_config
            data = inspect_config(text)
        except (OSError, UnicodeError, ValueError) as exc:
            QMessageBox.warning(self, "Import unavailable", "Cannot inspect this .conf file safely.")
            return
        self.imported_profile = True
        self.import_original = None
        self.import_source_name = None
        self.edit_name = None
        self.edit_revision = None
        self.edit_original = None
        self.profile_name.setReadOnly(False)
        self._set_editor_locked(False)
        self.install_button.setEnabled(False)
        self.peer_selector.blockSignals(True)
        self.peer_selector.clear()
        self.peer_selector.addItem("Peer 1 (preview)")
        self.peer_selector.blockSignals(False)
        self.current_peer_index = 0
        self.remove_peer_button.setEnabled(False)
        self.add_peer_button.setEnabled(False)
        self.profile_name.setText(path.stem)
        self.address.setText(data.address or "")
        self.listen_port.setValue(data.listen_port or 0)
        self.private_key.setText(data.private_key or "")
        self.interface_public_key.clear()  # do not disclose/derive private keys on import
        self.dns.setText(data.dns or "")
        self.mtu.setValue(data.mtu or 0)
        self.public_key.setText(data.first_peer_key or "")
        self.endpoint.setText(data.first_peer_endpoint or "")
        self.allowed_ips.setText(data.first_peer_allowed_ips or "")
        self.keepalive.setValue(data.first_peer_keepalive or 0)
        self.preshared_key.setText(data.first_peer_preshared_key or "")
        self.peer_states = [self._read_peer()]
        from ..core.profile_export import parse_supported_profile, ProfileValidationError
        try:
            draft = parse_supported_profile(path.stem, text)
        except ProfileValidationError:
            self._set_editor_locked(True)
            self.editor_note.setText(
                f"Read-only preview ({data.peer_count} peer(s)). Unsupported directives, "
                "hooks or syntax prevent any save/install. No options are silently dropped. "
                "The original external file remains unchanged; unsupported native "
                "options require an advanced editor (not available in personal v1)."
            )
        else:
            self.imported_profile = False
            # Preserve the imported, supported native document byte-for-byte
            # if unchanged. Field edits use the lossless rewrite of sections.
            self.import_original = text
            self.import_source_name = path.stem
            self.peer_states = list(draft.peers)
            self.peer_selector.blockSignals(True)
            self.peer_selector.clear()
            for i in range(len(self.peer_states)):
                self.peer_selector.addItem(f"Peer {i + 1}")
            self.peer_selector.setCurrentIndex(0)
            self.peer_selector.blockSignals(False)
            self.current_peer_index = -1
            self._switch_peer(0)
            self.add_peer_button.setEnabled(True)
            self.remove_peer_button.setEnabled(len(self.peer_states) > 1)
            self.install_button.setEnabled(not self.demo and helper_available())
            self.editor_note.setText(
                f"Imported {len(draft.peers)} supported peer(s) without executable hooks. "
                "Create Profile installs a native .conf, preserving supported "
                "original comments and formatting. Existing names cannot be overwritten."
            )

        self._show_profile_editor()

    def build_diagnostics(self):
        content, layout = self.new_content()
        layout.addLayout(page_heading("Diagnostics", "Read-only system information — no secrets in logs"))
        cards = QGridLayout()
        self.diagnostics_grid = cards
        self.diagnostics_cards = []
        self.diag_module = named_label("Not checked", "metricLabel")
        self.diag_tools = named_label("Not checked", "metricLabel")
        self.diag_route = named_label("Not checked", "metricLabel")
        self.diag_error = named_label("None observed", "metricLabel")
        for idx, (title, value) in enumerate((
            ("Kernel Module", self.diag_module),
            ("wg Version", self.diag_tools),
            ("Routing Check", self.diag_route),
            ("Last Inventory Warning", self.diag_error),
        )):
            card, inner = make_panel()
            inner.addWidget(named_label(title, "sectionTitle"))
            inner.addWidget(value)
            cards.addWidget(card, 0, idx)
            self.diagnostics_cards.append(card)
        layout.addLayout(cards)
        logs_frame, logs_layout = make_panel()
        logs_layout.addWidget(named_label("Recent Diagnostics", "sectionTitle"))
        self.log_summary = named_label("No session events yet.", "secondary")
        logs_layout.addWidget(self.log_summary)
        self.diag_logs = QTableWidget(0, 3)
        self.diag_logs.setHorizontalHeaderLabels(("Time", "Level", "Message"))
        self.diag_logs.verticalHeader().setVisible(False)
        self.diag_logs.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.diag_logs.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.diag_logs.setAlternatingRowColors(True)
        self.diag_logs.setShowGrid(False)
        self.diag_logs.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.diag_logs.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.diag_logs.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.diag_logs.setMinimumHeight(205)
        logs_layout.addWidget(self.diag_logs)
        layout.addWidget(logs_frame)
        layout.addWidget(named_label(
            "Detailed system journals and network routes are intentionally not exposed until "
            "secret-redaction and permission checks are implemented.", "secondary"))
        layout.addStretch()
        self.scroll_page(content)

    def build_settings(self):
        from .widgets import ToggleSwitch

        content, layout = self.new_content()
        layout.addLayout(page_heading(
            "Settings", "Application preferences and security boundaries"
        ))
        grid = QGridLayout()
        grid.setSpacing(14)
        self.settings_grid = grid
        self.settings_cards = []
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        def toggle_row(host: QVBoxLayout, label: str, *, enabled: bool = False,
                       checked: bool = False, reason: str = "") -> ToggleSwitch:
            row = QHBoxLayout()
            row.setContentsMargins(0, 3, 0, 3)
            title = named_label(label, "settingLabel")
            title.setToolTip(reason)
            row.addWidget(title, 1)
            toggle = ToggleSwitch()
            toggle.setAccessibleName(label)
            toggle.setChecked(checked)
            toggle.setEnabled(enabled)
            if reason:
                toggle.setToolTip(reason)
            row.addWidget(toggle, 0, Qt.AlignmentFlag.AlignRight)
            host.addLayout(row)
            return toggle

        application, form = make_panel()
        form.addWidget(named_label("⚙  Application", "sectionTitle"))
        pending_desktop = "Available after the Wayland / GNOME desktop integration gate."
        self.autostart_switch = toggle_row(
            form, "Start on login (autostart)",
            enabled=not self.demo,
            checked=autostart_enabled(),
            reason="Starts only the desktop app on your next login. "
                   "Never connects VPN profiles automatically or requires Polkit."
        )
        self.autostart_switch.toggled.connect(self._autostart_changed)
        toggle_row(form, "Show system tray icon", checked=True, reason=pending_desktop)
        toggle_row(form, "Show notifications", reason="Notification/redaction gate pending.")
        self.tray_close_switch = toggle_row(
            form, "Minimize to tray on close",
            enabled=QSystemTrayIcon.isSystemTrayAvailable(),
            checked=self.preferences.value("minimize_on_close", False, bool),
            reason="Requires an available system tray."
        )
        self.tray_close_switch.toggled.connect(
            lambda value: self.preferences.setValue("minimize_on_close", value)
        )
        self.version_label = named_label(
            f"Version {__version__} · WG Deck", "secondary"
        )
        self.version_label.setAccessibleName("WG Deck version")
        form.addWidget(self.version_label)
        form.addStretch()
        grid.addWidget(application, 0, 0)
        self.settings_cards.append(application)

        security, security_form = make_panel()
        security_form.addWidget(named_label("⬟  VPN Behavior", "sectionTitle"))
        privileged = "Requires the validated, authenticated Polkit helper."
        toggle_row(security_form, "Auto-connect last used profile", reason=privileged)
        toggle_row(security_form, "Manage DNS (via wg-quick)", reason=privileged)
        toggle_row(security_form, "Enable kill switch", reason=privileged)
        self.confirm_connection_switch = toggle_row(
            security_form, "Confirm Connect / Disconnect",
            enabled=True,
            checked=self.preferences.value("confirm_connection_changes", True, bool),
            reason="Shows an explicit confirmation before changing a VPN interface. "
                   "Polkit authentication remains required independently."
        )
        self.confirm_connection_switch.toggled.connect(
            lambda enabled: self.preferences.setValue("confirm_connection_changes", enabled)
        )
        security_form.addWidget(named_label(
            "Confirmation is independent of Polkit: disabling it never grants root access. "
            "Advanced VPN behavior above remains unavailable.",
            "secondary"
        ))
        security_form.addStretch()
        grid.addWidget(security, 0, 1)
        self.settings_cards.append(security)

        appearance, appearance_form = make_panel()
        appearance_form.addWidget(named_label("◉  Appearance", "sectionTitle"))
        appearance_form.addWidget(named_label("Theme", "secondary"))
        self.theme_choice = CleanComboBox()
        self.theme_choice.addItem("System (follow OS)", ThemeMode.SYSTEM.value)
        self.theme_choice.addItem("Light (canonical mock)", ThemeMode.LIGHT.value)
        self.theme_choice.addItem("Dark", ThemeMode.DARK.value)
        self.theme_choice.setCurrentIndex(
            self.theme_choice.findData(self.theme.mode.value)
        )
        self.theme_choice.currentIndexChanged.connect(self._theme_choice_changed)
        appearance_form.addWidget(self.theme_choice)
        self.effective_theme_label = named_label(
            f"Applied: {self.theme.effective.value.title()}", "secondary"
        )
        appearance_form.addWidget(self.effective_theme_label)
        appearance_form.addStretch()
        grid.addWidget(appearance, 1, 0)
        self.settings_cards.append(appearance)

        helper, helper_form = make_panel()
        helper_form.addWidget(named_label("⬟  Privileged Operations", "sectionTitle"))
        helper_form.addWidget(named_label(
            "Polkit helper: installed" if helper_available()
            else "Polkit helper: not installed", "secondary"
        ))
        helper_form.addWidget(named_label(
            "Connections and reading/exporting configs use separate short-lived Polkit grants "
            "(typically around 5 minutes). Creating, modifying and deleting native "
            "profiles still require authentication for each request. "
            "The system controls when to ask again.",
            "secondary"
        ))
        helper_form.addStretch()
        grid.addWidget(helper, 1, 1)
        self.settings_cards.append(helper)
        layout.addLayout(grid)

        # Product attribution lives in the sidebar, not inside Settings.
        layout.addStretch()
        self.scroll_page(content)

    def _refresh_wgdeck_header_logo(self, effective: str):
        try:
            self.wgdeck_header_logo.setPixmap(
                wg_deck_logo_pixmap(effective, width=184, height=38)
            )
        except (OSError, ValueError):
            self.wgdeck_header_logo.setText("WG Deck")

    def _refresh_matt88_logo(self, effective: str):
        narrow = self.sidebar_frame.width() <= 160
        width, height = (76, 20) if narrow else (86, 22)
        self.sidebar_matt88_logo.setFixedSize(width, height)
        try:
            self.sidebar_matt88_logo.setPixmap(
                matt88_logo_pixmap(effective, width=width, height=height)
            )
            self.sidebar_matt88_logo.setText("")
        except (OSError, ValueError):
            self.sidebar_matt88_logo.setPixmap(QPixmap())
            self.sidebar_matt88_logo.setText("matt88.it")

    def _autostart_changed(self, enabled: bool):
        try:
            set_autostart(enabled)
        except AutostartError as exc:
            self.autostart_switch.blockSignals(True)
            self.autostart_switch.setChecked(autostart_enabled())
            self.autostart_switch.blockSignals(False)
            QMessageBox.warning(self, "Autostart unchanged", str(exc))
            return
        self.statusBar().showMessage(
            "WG Deck will start at login (without connecting VPNs)."
            if enabled else "WG Deck autostart disabled.", 7000
        )

    def _theme_choice_changed(self, _index: int):
        choice = self.theme_choice.currentData()
        self.theme.set_mode(choice)

    def _theme_changed(self, effective: str):
        index = self.pages.currentIndex()
        for i, button in enumerate(self.nav_buttons):
            button.setIcon(vector_icon(NAV[i], "#FFFFFF" if i == index else self.theme.tokens.secondary))
        for button in self.findChildren(QPushButton):
            icon_name = button.property("wgmIconName")
            if icon_name:
                fg = "#FFFFFF" if button.objectName() == "primary" else self.theme.tokens.secondary
                button.setIcon(vector_icon(icon_name, fg))
        if hasattr(self, "effective_theme_label"):
            self.effective_theme_label.setText(f"Applied: {effective.title()}")
        if hasattr(self, "sidebar_matt88_logo"):
            self._refresh_matt88_logo(effective)
        if hasattr(self, "wgdeck_header_logo"):
            self._refresh_wgdeck_header_logo(effective)
        self.fill_tables()

    def setup_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.statusBar().showMessage("Tray unsupported on this session; main window works normally.")
            return
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.menu = QMenu(self)
        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip(
            "WG Deck — WireGuard profiles" if helper_available() and not self.demo
            else "WG Deck — read-only"
        )
        self.refresh_tray()
        self.tray.show()
        # Closing the window still quits, to prevent an invisible resident process.

    def refresh_tray(self):
        if self.tray is None:
            return
        self.menu.clear()
        title = self.menu.addAction("WG Deck")
        title.setEnabled(False)
        if self.demo:
            demo_title = self.menu.addAction("DEMO DATA — no real tunnels")
            demo_title.setEnabled(False)
        self.menu.addSeparator()
        for profile in self.inventory.profiles[:15]:
            label = f"{'●' if profile.state == TunnelState.UP else '○'}  {profile.name}"
            sub = self.menu.addMenu(label)
            status = sub.addAction(
                "Interface UP" if profile.state == TunnelState.UP
                else "Interface DOWN" if profile.state == TunnelState.DOWN
                else "Unknown"
            )
            status.setEnabled(False)
            can_manage = (
                not self.demo and connection_available()
                and not self._busy_action
                and profile.state != TunnelState.UNKNOWN
            )
            op = "down" if profile.state == TunnelState.UP else "up"
            action = sub.addAction("Disconnect" if op == "down" else "Connect")
            action.setEnabled(can_manage)
            action.triggered.connect(
                lambda checked=False, action_name=op, profile_name=profile.name:
                    self.request_operation(action_name, profile_name)
            )
            details = sub.addAction("Open Manager")
            details.triggered.connect(self.show_manager)
        self.menu.addSeparator()
        if not helper_available() and not self.demo:
            note = self.menu.addAction("Install helper to enable VPN controls")
            note.setEnabled(False)
        self.menu.addSeparator()
        self.menu.addAction("Open Manager", self.show_manager)
        self.menu.addAction("Quit", self.quit_application)
        self.tray.setContextMenu(self.menu)

    def quit_application(self):
        self._quit_requested = True
        self.close()
        QApplication.instance().quit()

    def closeEvent(self, event):
        if (
            not self._quit_requested
            and self.tray is not None
            and self.tray.isVisible()
            and self.preferences.value("minimize_on_close", False, bool)
        ):
            self.hide()
            event.ignore()
            return
        super().closeEvent(event)

    def show_manager(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def show_profile_details(self, row: int, column: int):
        source = self.sender()
        profiles = getattr(source, "visible_profiles", [])
        if not 0 <= row < len(profiles):
            return
        profile = profiles[row]
        status = {
            TunnelState.UP: "Interface UP — handshake may still be absent",
            TunnelState.DOWN: "Interface down",
            TunnelState.UNKNOWN: "Unknown (insufficient permission or observation)",
            TunnelState.ERROR: "Error",
        }.get(profile.state, "Unknown")
        description = "\n".join((
            f"Name: {profile.name}",
            f"Status: {status}",
            f"Endpoint: {profile.endpoint or 'unavailable'}",
            f"Latest handshake: {safe_handshake(profile.last_handshake)}",
            f"RX: {format_bytes(profile.rx_bytes)}",
            f"TX: {format_bytes(profile.tx_bytes)}",
            "",
            "No key material is read or displayed; no system action was performed.",
        ))
        QMessageBox.information(self, "Profile details (read-only)", description)

    def refresh(self):
        if self.demo:
            self.accept_inventory(demo_inventory())
            return
        if self._refreshing:
            return
        self._refreshing = True
        worker = InventoryWorker()
        worker.signals.finished.connect(self.accept_inventory)
        self._worker = worker
        self.pool.start(worker)

    def accept_inventory(self, result: Inventory):
        self._refreshing = False
        self.inventory = result
        profiles = result.profiles
        up = sum(p.state == TunnelState.UP for p in profiles)
        down = sum(p.state == TunnelState.DOWN for p in profiles)
        rx = sum(p.rx_bytes or 0 for p in profiles)
        tx = sum(p.tx_bytes or 0 for p in profiles)
        observable = all(
            p.rx_bytes is not None and p.tx_bytes is not None
            for p in profiles if p.state == TunnelState.UP
        )
        current = {
            p.name: (p.rx_bytes, p.tx_bytes)
            for p in profiles if p.state == TunnelState.UP
            and p.rx_bytes is not None and p.tx_bytes is not None
        }
        now = time.monotonic()
        rate = ""
        if self._traffic_sample is not None and current and observable:
            earlier, old = self._traffic_sample
            elapsed = now - earlier
            if elapsed >= 1:
                common = current.keys() & old.keys()
                if common and all(current[n][0] >= old[n][0]
                                  and current[n][1] >= old[n][1] for n in common):
                    rate_rx = sum(current[n][0] - old[n][0] for n in common) / elapsed
                    rate_tx = sum(current[n][1] - old[n][1] for n in common) / elapsed
                    rate = f"  |  {format_bytes(rate_rx)}/s ↓  {format_bytes(rate_tx)}/s ↑"
        self._traffic_sample = (now, current) if observable else None
        for label, value in zip(self.metrics, (
            str(len(profiles)), str(up), str(down),
            format_bytes(rx + tx) if observable else "Unavailable",
        )):
            label.setText(value)
        for detail, value in zip(self.metric_details, (
            f"{up} connected",
            f"{up / len(profiles):.0%} online" if profiles else "No profiles",
            f"{down / len(profiles):.0%} offline" if profiles else "No profiles",
            (f"↓ {format_bytes(rx)}  ↑ {format_bytes(tx)}{rate}"
             if observable else "Traffic counters unavailable"),
        )):
            detail.setText(value)
        if result.warnings:
            self.dashboard_note.setText("  •  ".join(result.warnings))
        else:
            self.dashboard_note.setText(
                "Read-only observation. Interface UP does not guarantee recent peer handshake."
            )
        self.diag_tools.setText(result.wg_version)
        self.diag_module.setText("Not checked (wg tools ≠ kernel module)")
        self.diag_route.setText("Not verified (read-only foundation)")
        self.diag_error.setText(result.warnings[0] if result.warnings else "None observed")
        self.log_summary.setText(
            "Last inventory refresh: " + datetime.now().strftime("%H:%M:%S") +
            f" — {len(profiles)} visible profile(s), {up} observed UP."
        )
        self._fill_diagnostics()
        self.fill_tables()
        self.refresh_tray()

    def _fill_diagnostics(self):
        when = datetime.now().strftime("%H:%M:%S")
        if self.demo:
            events = [
                ("DEMO", "SAMPLE", "Synthetic inventory: 5 fictional profiles"),
                ("DEMO", "SAMPLE", "Sample peer transfer totals are not live traffic"),
                ("DEMO", "SAMPLE", "No WireGuard commands were executed"),
            ]
        else:
            events = [
                (when, "INFO", "Read-only profile inventory refreshed"),
                (when, "INFO", f"{len(self.inventory.profiles)} visible interface/profile names"),
            ]
            events.extend(
                (when, "WARN", warning)
                for warning in self.inventory.warnings[:4]
            )
        self.diag_logs.setRowCount(len(events))
        for row, values in enumerate(events):
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.diag_logs.setItem(row, column, item)
            self.diag_logs.setRowHeight(row, 30)

    def fill_tables(self, *unused):
        if hasattr(self, "dashboard_table"):
            self.dashboard_table.populate(
                self.inventory.profiles, self.dashboard_search.text(),
                not self.demo and connection_available() and not self._busy_action,
                not self.demo and helper_available() and not self._busy_action,
            )
        if hasattr(self, "profiles_table"):
            self.profiles_table.populate(
                self.inventory.profiles, self.profiles_search.text(),
                not self.demo and connection_available() and not self._busy_action,
                not self.demo and helper_available() and not self._busy_action,
            )
