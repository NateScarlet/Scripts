# -*- coding=UTF-8 -*-
"""Show a notify bubble.   """
from __future__ import absolute_import, print_function, unicode_literals

import sys

from Qt.QtCore import Property, Qt, QTimer, QUrl
from Qt.QtWidgets import QApplication, QBoxLayout, QWidget

try:
    from PySide.QtDeclarative import QDeclarativeView as QQuickView
except ImportError:
    from PySide2.QtQuick import QQuickView


class NotifyContainer(QWidget):
    instance = None
    __is_initiated = False

    def __new__(cls, parent=None):
        if not isinstance(cls.instance, NotifyContainer):
            cls.instance = super(NotifyContainer, cls).__new__(cls, parent)
        return cls.instance

    def __init__(self, parent=None):
        if self.__is_initiated:
            return

        super(NotifyContainer, self).__init__(parent)
        layout = QBoxLayout(QBoxLayout.BottomToTop, self)
        layout.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            # | Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_QuitOnClose, True)
        self.geo = QApplication.desktop().availableGeometry(self)

        self.__is_initiated = True

        self.show()

    def paintEvent(self, event):
        # Match to target geo.
        if self.geometry() != self.geo:
            self.setUpdatesEnabled(False)
            self.setGeometry(self.geo)
            self.setUpdatesEnabled(True)
        super(NotifyContainer, self).paintEvent(event)

    def childEvent(self, event):
        super(NotifyContainer, self).childEvent(event)
        if event.child().isWidgetType():
            if event.removed():
                child_widgets = [i for i in self.children()
                                 if i.isWidgetType()]
                if not child_widgets:
                    self.close()


class Notify(QQuickView):
    height_ = Property(int,
                       QQuickView.height,
                       QQuickView.setFixedHeight)
    width_ = Property(int,
                      QQuickView.width,
                      QQuickView.setFixedWidth)

    def __init__(self, parent=None):
        parent = parent or NotifyContainer()
        super(Notify, self).__init__(parent)
        layout = parent.layout()
        if layout:
            layout.addWidget(self, alignment=layout.alignment())
        self.setStyleSheet("background:transparent;")
        self.setAttribute(Qt.WA_DeleteOnClose, True)

    @classmethod
    def from_file(cls, file, **data):
        """Construct from file path.

        Args:
            file (str): qml file path.
            data (dict, optional): Data will be used in qml as `DATA`.
        """

        ret = Notify()
        context = ret.rootContext()
        context.setContextProperty('DATA', data)
        context.setContextProperty('VIEW', ret)
        ret.setSource(QUrl.fromLocalFile(file))
        QApplication.processEvents()
        return ret


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
        Notify.from_file(qml_file, text=random.choice(all_msg))

    def _delay_run(times):
        if times <= 0:
            return
        timer = QTimer()
        all_timer.append(timer)
        timer.setSingleShot(True)
        timer.timeout.connect(_run)
        timer.timeout.connect(lambda: _delay_run(times - 1))
        timer.start(random.randint(0, 300))

    _delay_run(1)
    _delay_run(3)
    _delay_run(30)

    sys.exit(app.exec_())
