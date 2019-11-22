import sys
import mainwindow
from PySide2.QtWidgets import QApplication

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = mainwindow.MainWindow()
    window.show()
    sys.exit(app.exec_())
