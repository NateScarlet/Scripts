# -*- coding=UTF-8 -*-
from __future__ import print_function, unicode_literals, absolute_import
import logging
import logging.config
from notify import qml_notify

import sys
import os
from shadowsky_checkin import is_logged_in, login, checkin, get_status, LOG_PATH

from Qt.QtWidgets import QApplication, QDialog, QVBoxLayout, QLineEdit, QLabel, QDialogButtonBox


from collections import namedtuple


class QtHandler(logging.Handler):
    qml_file = os.path.abspath(os.path.join(__file__, '../notify.qml'))

    def emit(self, record):
        qml_notify(self.qml_file, text=self.format(record))


LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'simple': {
            'format': '%(levelname)-6s[%(asctime)s]: %(message)s'
        }
    },
    'handlers': {
        'qt': {
            'class': '{}.QtHandler'.format(__name__),
            'level': 'INFO'
        },
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG'
        },
        'file': {
            'class': 'logging.FileHandler',
            'formatter': 'simple',
            'level': 'INFO',
            'filename': LOG_PATH,
            'encoding': 'utf-8'
        }
    },
    'root': {
        'handlers': ['qt', 'console', 'file'],
        'level': 'DEBUG'
    }
}

LoginInfo = namedtuple('LoginInfo', ['email', 'password'])


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super(LoginDialog, self).__init__(parent)
        self.setWindowTitle('shadowsky签到')

        layout = QVBoxLayout(self)
        self.emailEdit = QLineEdit(self)
        self.emailEdit.setPlaceholderText('邮箱地址')
        self.passwordEdit = QLineEdit(self)
        self.passwordEdit.setEchoMode(QLineEdit.Password)
        self.passwordEdit.setPlaceholderText('密码')
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                               accepted=self.accept,
                               rejected=self.reject)

        layout.addWidget(QLabel('邮箱地址'))
        layout.addWidget(self.emailEdit)
        layout.addWidget(QLabel('密码'))
        layout.addWidget(self.passwordEdit)
        layout.addWidget(box)


def ask_login_info():
    dialog = LoginDialog()
    if dialog.exec_():
        return LoginInfo(dialog.emailEdit.text(),
                         dialog.passwordEdit.text())
    raise RuntimeError('Cancelled')


def main():
    logging.config.dictConfig(LOGGING_CONFIG)

    APP = QApplication(sys.argv)

    while not is_logged_in():
        login(*ask_login_info())
        APP.processEvents()
    checkin()
    APP.processEvents()
    try:
        msg = '已用 {0.used} GB, 剩余 {0.remain} GB'.format(get_status())
        logging.info(msg)
    except RuntimeError:
        logging.error('获取流量信息失败')
    sys.exit(APP.exec_())


if __name__ == '__main__':
    main()
