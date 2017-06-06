# usr/bin/env python
# -*- coding=UTF-8 -*-

import os
import sys
import locale
from subprocess import call

import PySide.QtCore, PySide.QtGui
from PySide.QtGui import QMainWindow, QApplication, QFileDialog

from ui_CGTeamWorkTool import Ui_MainWindow
from config import Config
from sync import Sync
from sync import LoginError

VERSION = 0.1
SYS_CODEC = locale.getdefaultlocale()[1]
SCRIPT_CODEC = 'UTF-8'

 
def pause():
    call('PAUSE', shell=True)

class MainWindow(QMainWindow, Ui_MainWindow, Sync, Config):

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        Config.__init__(self)
        Sync.__init__(self)
        self.setupUi(self)
        self.versionLabel.setText('v{}'.format(VERSION))

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
        self.downloadButton.clicked.connect(self.exec_downlowd_button)

    def connect_edits(self):
        for edit, key in self.edits_key.iteritems():
            if type(edit) == PySide.QtGui.QLineEdit:
                edit.textChanged.connect(lambda text, k=key: self.editConfig(k, text))
                edit.textChanged.connect(self.update)
            elif type(edit) == PySide.QtGui.QCheckBox:
                edit.stateChanged.connect(lambda state, k=key: self.editConfig(k, state))
                edit.stateChanged.connect(self.update)
            elif type(edit) == PySide.QtGui.QComboBox:
                edit.editTextChanged.connect(lambda text, k=key: self.editConfig(k, text))
            else:
                print(u'待处理的控件: {} {}'.format(type(edit), edit))

    def update(self):
        self.set_edits()
        self.set_list_widget()

    def set_edits(self):
        for q, k in self.edits_key.iteritems():
            try:
                if isinstance(q, PySide.QtGui.QLineEdit):
                    q.setText(self.config[k])
                if isinstance(q, PySide.QtGui.QCheckBox):
                    q.setCheckState(PySide.QtCore.Qt.CheckState(self.config[k]))
            except KeyError as e:
                print(e)

    def set_list_widget(self):
        list = self.listWidget
        cfg = self.config

        self.get_file_list()
        list.clear()
        for i in cfg['video_list']:
            list.addItem(u'将下载: {}'.format(i))
                
    def exec_dest_button(self):
        fileDialog = QFileDialog()
        dir = fileDialog.getExistingDirectory(dir=os.path.dirname(self.config['DEST']))
        if dir:
            self.config['DEST'] = dir
            self.update()

    def exec_downlowd_button(self):
        self.download_videos()


def main():
    call(u'CHCP 936 & TITLE CGTWBatchDownload_v{} & CLS'.format(VERSION).encode('GBK'), shell=True)
    app = QApplication(sys.argv)
    frame = MainWindow()
    frame.show()
    sys.exit(app.exec_())
  
if __name__ == '__main__':
    try:
        main()
    except SystemExit as e:
        exit(e)
    except LoginError as e:
        print(e)
        pause()
    except:
        import traceback
        traceback.print_exc()