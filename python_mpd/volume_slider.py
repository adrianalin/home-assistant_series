from PySide2 import QtWidgets
from PySide2.QtCore import Signal

WIDTH = 150


class VolumeWidget(QtWidgets.QProgressBar):
    valueChanged = Signal(int)

    def __init__(self):
        super().__init__()
        self.setTextVisible(False)
        self.setRange(0, 100)
        self.setValue(100)
        self.setFixedHeight(25)
        self.setMaximumWidth(WIDTH)
        self.dragging = False

        self.setStyleSheet(
            """
            QProgressBar {
                margin: 10px;
                height: 5px;
                border: 0px solid #555;
                border-radius: 2px;
                background-color: #666;
            }

            QProgressBar::chunk {
                background-color: white;
                border-radius: 2px;
                width: 1px;
            }
            """
        )

    def update_position(self, level):
        self.setValue(level)

    def mousePressEvent(self, event):
        self.dragging = True
        value = int((event.x() / self.width()) * self.maximum())
        self.setValue(value)

    def mouseMoveEvent(self, event):
        if self.dragging and 0 <= event.x() <= WIDTH:
            value = int((event.x() / self.width()) * self.maximum())
            self.setValue(value)
            self.valueChanged.emit(value)

    def mouseReleaseEvent(self, event):
        self.dragging = False