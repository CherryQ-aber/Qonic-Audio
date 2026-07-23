from PySide6.QtCore import QObject, Property, Signal

from ui_next.bridge.capabilities import CapabilityGate


class BaseViewModel(QObject):
    """Small QObject base for QML-facing state objects."""

    errorOccurred = Signal(str)
    statusMessageChanged = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        capability_gate: CapabilityGate | None = None,
    ) -> None:
        super().__init__(parent)
        self._capability_gate = capability_gate or CapabilityGate()
        self._status_message = ""

    @Property(str, notify=statusMessageChanged)
    def statusMessage(self) -> str:
        return self._status_message

    def set_status_message(self, message: str) -> None:
        if self._status_message == message:
            return
        self._status_message = message
        self.statusMessageChanged.emit(message)

    @Property(QObject, constant=True)
    def capabilityGate(self) -> CapabilityGate:
        return self._capability_gate

    @Property(str, constant=True)
    def capabilitySummary(self) -> str:
        return self._capability_gate.summary

    def allows_capability(self, capability: str) -> bool:
        return self._capability_gate.allows(capability)

    def block_capability(self, capability: str) -> str:
        message = self._capability_gate.blockedMessage(capability)
        self.set_status_message(message)
        return message
