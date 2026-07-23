from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QFrame, QListView


def make_hard_edge_combo_box(parent=None):
    combo = QComboBox(parent)
    combo.setObjectName("HardEdgeComboBox")
    combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    popup_view = QListView(combo)
    popup_view.setObjectName("HardEdgeComboPopup")
    popup_view.setFrameShape(QFrame.Shape.NoFrame)
    popup_view.setLineWidth(0)
    popup_view.setMidLineWidth(0)
    popup_view.setUniformItemSizes(True)
    popup_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    popup_view.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    popup_view.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    combo.setView(popup_view)
    return combo
