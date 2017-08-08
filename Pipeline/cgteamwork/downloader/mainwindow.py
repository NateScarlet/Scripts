# usr/bin/env python
# -*- coding=UTF-8 -*-

import os
import sys
from subprocess import call

import PySide.QtCore
import PySide.QtGui
from PySide.QtGui import QMainWindow, QApplication, QFileDialog

from ui_mainwindow import Ui_MainWindow
from config import Config
from sync import Sync
from sync import LoginError

from files import get_encoded
import console

__version__ = '0.1.1'


class MainWindow(QMainWindow, Ui_MainWindow, Sync, Config):

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        Config.__init__(self)
        Sync.__init__(self)
        self.setupUi(self)
        self.versionLabel.setText('v{}'.format(__version__))

        self.edits_key = {
            self.databaseEdit: 'DATABASE',
            self.moduleEdit: 'MODULE',
            self.serverEdit: 'SERVER',
            self.pipelineEdit: 'PIPELINE',
            self.destEdit: 'DEST',
            self.shotPrefixEdit: 'SHOT_PREFIX'
        }

        self.update()

        self.connect_buttons()
        self.connect_edits()

    def connect_buttons(self):
        self.destButton.clicked.connect(self.exec_dest_button)
        self.actionDownload.triggered.connect(self.downlowd)

    def connect_edits(self):
        for edit, key in self.edits_key.iteritems():
            if type(edit) == PySide.QtGui.QLineEdit:
                edit.textChanged.connect(
                    lambda text, k=key: self.editConfig(k, text))
                edit.textChanged.connect(self.update)
            elif type(edit) == PySide.QtGui.QCheckBox:
                edit.stateChanged.connect(
                    lambda state, k=key: self.editConfig(k, state))
                edit.stateChanged.connect(self.update)
            elif type(edit) == PySide.QtGui.QComboBox:
                edit.editTextChanged.connect(
                    lambda text, k=key: self.editConfig(k, text))
            else:
                print(u'待处理的控件: {} {}'.format(type(edit), edit))

    def update(self):
        self.set_edits()
        self.set_list_widget()
        self.set_button_enabled()

    def set_edits(self):
        for q, k in self.edits_key.iteritems():
            try:
                if isinstance(q, PySide.QtGui.QLineEdit):
                    q.setText(self.config[k])
                if isinstance(q, PySide.QtGui.QCheckBox):
                    q.setCheckState(
                        PySide.QtCore.Qt.CheckState(self.config[k]))
            except KeyError as e:
                print(e)

    def set_list_widget(self):
        widget = self.listWidget
        cfg = self.config

        self.get_file_list()
        widget.clear()
        for i in cfg['video_list']:
            widget.addItem(u'将下载: {}'.format(i))

    def exec_dest_button(self):
        fileDialog = QFileDialog()
        dest = fileDialog.getExistingDirectory(
            dest=os.path.dirname(self.config['DEST']))
        if dest:
            self.config['DEST'] = dest
            self.update()

    def downlowd(self):
        self.download_videos()

    def set_button_enabled(self):
        self.downloadButton.setEnabled(bool(self.config['DEST']))


def main():
    call(get_encoded(u'CHCP 936 & TITLE CGTWBatchDownload_v{} & CLS'.format(
        __version__)), shell=True)
    app = QApplication(sys.argv)
    frame = MainWindow()
    frame.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    try:
        main()
    except SystemExit as ex:
        exit(ex)
    except LoginError as ex:
        print(ex)
        console.pause()
