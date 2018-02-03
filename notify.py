# -*- coding=UTF-8 -*-
"""Show a notify bubble.   """
from __future__ import absolute_import, print_function, unicode_literals

import sys

from Qt.QtCore import (Property, QObject, QPoint, QPropertyAnimation, Qt,
                       QTimer, QUrl)
from Qt.QtWidgets import QApplication

try:
    from PySide.QtDeclarative import QDeclarativeView
except:
    from PySide2.QtDeclarative import QDeclarativeView


class QMLNotifyView(QDeclarativeView):
    display_time = 3000
    last_instance = None

    def __init__(self, parent=None):
        super(QMLNotifyView, self).__init__(parent)

        self.setResizeMode(QDeclarativeView.SizeRootObjectToView)
        self.setContentsMargins(8, 8, 8, 8)
        self.setWindowFlags(Qt.Window
                            | Qt.Tool
                            | Qt.FramelessWindowHint
                            | Qt.WindowStaysOnTopHint
                            | Qt.X11BypassWindowManagerHint)
        self.setStyleSheet("background:transparent;")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_QuitOnClose, True)

        timer = QTimer()
        timer.setSingleShot(True)
        self.display_timer = timer

        anim = QPropertyAnimation(self, b'opacity')
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setDuration(4000)
        self.dispear_anim = anim

        self.display_timer.timeout.connect(self.dispear_anim.start)
        self.dispear_anim.finished.connect(self.close)

        self.prev = QMLNotifyView.last_instance
        QMLNotifyView.last_instance = self

    def enterEvent(self, event):
        self.display_timer.stop()
        self.dispear_anim.stop()
        self.setWindowOpacity(1)
        event.accept()

    def leaveEvent(self, event):
        self.display_timer.start()
        event.accept()

    def closeEvent(self, event):
        if QMLNotifyView.last_instance is self:
            QMLNotifyView.last_instance = None
        event.accept()

    def show(self):
        super(QMLNotifyView, self).show()
        self.display_timer.start(self.display_time)
        desktop = QApplication.instance().desktop()
        if self.prev is None:
            pos = (desktop.availableGeometry().bottomRight()
                   - QPoint(10, 10))
        else:
            pos = self.prev.geometry().topRight() - QPoint(0, 10)
        pos -= QPoint(self.width(), self.height())
        self.move(pos)

    opacity = Property(float, QDeclarativeView.windowOpacity,
                       QDeclarativeView.setWindowOpacity)


def qml_notify(qml_file, data=None):
    """Show a qml file as a bubble.

    Args:
        qml_file (str): qml file path.
        data (dict, optional): Data will be used in qml as `DATA`.
    """

    view = QMLNotifyView()
    context = view.rootContext()
    context.setContextProperty('DATA', data)
    view.setSource(QUrl.fromLocalFile(qml_file))
    view.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    qml_notify('notify.qml', {'text': 'test1<b>测试消息1</b>'})
    qml_notify('notify.qml', {
               'text': 'test2<i>测试消息2</i> too loooooooooooooong'})
    sys.exit(app.exec_())
