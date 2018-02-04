# -*- coding=UTF-8 -*-
"""Show a notify bubble.   """
from __future__ import absolute_import, print_function, unicode_literals

import sys

from Qt.QtCore import (Property, QEasingCurve, QPropertyAnimation, Qt, QTimer,
                       QUrl)
from Qt.QtWidgets import QApplication, QBoxLayout, QWidget

try:
    from PySide.QtDeclarative import QDeclarativeView as QQuickView
except ImportError:
    from PySide2.QtQuick import QQuickView


class NotifyContainer(QWidget):
    def __init__(self, parent=None):
        super(NotifyContainer, self).__init__(parent)
        layout = QBoxLayout(QBoxLayout.BottomToTop, self)
        layout.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.setWindowFlags(Qt.Window
                            | Qt.Tool
                            | Qt.FramelessWindowHint
                            | Qt.WindowStaysOnTopHint
                            | Qt.X11BypassWindowManagerHint)
        self.setStyleSheet("background:transparent;")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_QuitOnClose, True)
        self.showFullScreen()

    def childEvent(self, event):
        if event.child().isWidgetType():
            geo = QApplication.desktop().availableGeometry(self)
            if not geo.contains(self.geometry()):
                self.resize(geo.size())
            if event.removed():
                for i in self.children():
                    if i.isWidgetType():
                        return
                self.close()

    def closeEvent(self, event):
        if QMLNotifyView.container is self:
            QMLNotifyView.container = None


class QMLNotifyView(QQuickView):
    display_time = 3000
    container = None

    def __init__(self, parent=None):
        parent = parent or self.get_container()
        super(QMLNotifyView, self).__init__(parent)
        parent_layout = parent.layout()
        parent_layout.addWidget(self, alignment=parent_layout.alignment())
        self.setContentsMargins(8, 8, 8, 8)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # For closing animation.
        self.is_closing = False
        anim = QPropertyAnimation(self, b'view_height')
        anim.setEndValue(0)
        anim.setDuration(500)
        anim.setEasingCurve(QEasingCurve.InQuad)
        anim.finished.connect(self.close)
        self._close_anim = anim

    def get_container(self):
        if not isinstance(QMLNotifyView.container, QWidget):
            QMLNotifyView.container = NotifyContainer()
        return QMLNotifyView.container

    def closeEvent(self, event):
        if self.is_closing:
            event.accept()
            return

        event.ignore()
        self.is_closing = True
        self._close_anim.start()

    view_height = Property(int,
                           QQuickView.height,
                           QQuickView.setFixedHeight)


def qml_notify(qml_file, **data):
    """Show a qml file as a bubble.

    Args:
        qml_file (str): qml file path.
        data (dict, optional): Data will be used in qml as `DATA`.
    """

    view = QMLNotifyView()
    context = view.rootContext()
    context.setContextProperty('DATA', data)
    context.setContextProperty('VIEW', view)
    view.setSource(QUrl.fromLocalFile(qml_file))
    view.show()
    QApplication.processEvents()


if __name__ == "__main__":
    import os
    import time
    import random
    app = QApplication(sys.argv)
    all_msg = [
        'test1<b>测试消息1</b>',
        'test2<i>测试消息2</i> too loooooooooooooong',
        'test3<span style="color:red">测试消息3</span>',
        'test4 测试消息4'
    ]
    all_timer = []
    qml_file = os.path.abspath(os.path.join(__file__, '../notify.qml'))

    def _run():
        qml_notify(qml_file, text=random.choice(all_msg))

    def _delay_run(times):
        if times <= 0:
            return
        timer = QTimer()
        all_timer.append(timer)
        timer.setSingleShot(True)
        timer.timeout.connect(_run)
        timer.timeout.connect(lambda: _delay_run(times-1))
        timer.start(random.randint(0, 1000))

    _delay_run(30)

    sys.exit(app.exec_())
