"""Reusable painted controls that follow ThemeManager tokens, not the OS style."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QIntValidator
from PySide6.QtWidgets import QAbstractButton, QComboBox, QLineEdit

from .theme import LIGHT


class ToggleSwitch(QAbstractButton):
    """Mock-aligned, accessible checkable switch; honors disabled state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(40, 22)
        self.setAccessibleName("Setting toggle")

    def sizeHint(self):
        return QSize(40, 22)

    def paintEvent(self, _event):
        tokens = getattr(getattr(self.window(), "theme", None), "tokens", LIGHT)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        checked = self.isChecked()
        bg = (
            tokens.accent if checked and self.isEnabled()
            else tokens.disabled_bg if not self.isEnabled()
            else tokens.inactive
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(QRectF(1, 2, 38, 18), 9, 9)
        painter.setBrush(QColor("#FFFFFF" if self.isEnabled() else tokens.disabled_fg))
        x = 22 if checked else 4
        painter.drawEllipse(QRectF(x, 4, 14, 14))
        painter.end()


class NumericField(QLineEdit):
    """Styled numeric entry with 0 = automatic/disabled.

    QSpinBox's Qt style subcontrol layout rendered its text as blank on the
    owner's GNOME/Wayland host, despite a correct internal value. A genuine
    QLineEdit plus QIntValidator avoids platform spinbox painting entirely.
    It retains the value()/setValue() API used by profile serialization.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("numericField")
        self._minimum = 0
        self._maximum = 65535
        self._empty_label = "Automatic"
        self.setValidator(QIntValidator(self._minimum, self._maximum, self))
        self.setMinimumHeight(40)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setPlaceholderText(self._empty_label)
        self.setToolTip("Leave empty for Automatic; enter a number otherwise")
        self.editingFinished.connect(self._normalize)

    def setRange(self, minimum: int, maximum: int) -> None:
        if minimum > maximum or minimum < 0:
            raise ValueError("Invalid numeric field range")
        self._minimum, self._maximum = int(minimum), int(maximum)
        self.setValidator(QIntValidator(self._minimum, self._maximum, self))
        self.setValue(self.value())

    def setSpecialValueText(self, label: str) -> None:
        self._empty_label = label
        self.setPlaceholderText(label)

    def value(self) -> int:
        raw = self.text().strip()
        if not raw:
            return 0
        try:
            value = int(raw)
        except ValueError:
            return 0
        return value if self._minimum <= value <= self._maximum else 0

    def setValue(self, value: int) -> None:
        number = int(value)
        if number < self._minimum or number > self._maximum:
            raise ValueError("Numeric field value outside configured range")
        self.setText("" if number == 0 else str(number))

    def _normalize(self) -> None:
        # An intermediate partial value is never propagated to the VPN parser.
        self.setValue(self.value())



class CleanComboBox(QComboBox):
    """Native combo behavior with a theme-painted chevron, no OS arrow glitch."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cleanCombo")
        self.setMinimumHeight(40)
        self.setMinimumWidth(100)
        self.setAccessibleDescription("Choose an item from the dropdown list")

    def paintEvent(self, event):
        super().paintEvent(event)
        tokens = getattr(getattr(self.window(), "theme", None), "tokens", LIGHT)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(tokens.secondary))
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        center_x = self.width() - 17
        center_y = self.height() / 2
        painter.drawLine(QPointF(center_x - 4.5, center_y - 2),
                         QPointF(center_x, center_y + 2.5))
        painter.drawLine(QPointF(center_x, center_y + 2.5),
                         QPointF(center_x + 4.5, center_y - 2))
        painter.end()
