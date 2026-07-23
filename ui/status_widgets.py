from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class StatusCard(QFrame):
    """Compact dashboard card for high-level runtime status."""

    def __init__(self, title, value="--", subtitle="", parent=None):
        super().__init__(parent)
        self.setObjectName("StatusCard")

        self.title_label = QLabel(title)
        self.title_label.setObjectName("StatusCardTitle")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatusCardValue")

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("StatusCardSubtitle")
        self.subtitle_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)

    def set_value(self, value, subtitle=None):
        self.value_label.setText(str(value))
        if subtitle is not None:
            self.subtitle_label.setText(str(subtitle))


class StatusPill(QLabel):
    """Small colored status label used in tables and summaries."""

    VALID_TONES = {
        "neutral",
        "success",
        "warning",
        "processing",
        "unsaved",
        "error",
    }

    def __init__(self, text="", tone="neutral", parent=None):
        super().__init__(text, parent)
        self.setObjectName("StatusPill")
        self.set_tone(tone)

    def set_tone(self, tone):
        if tone not in self.VALID_TONES:
            tone = "neutral"

        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)
