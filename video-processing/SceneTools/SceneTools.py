# usr/bin/env python
# -*- coding=UTF-8 -*-
# SceneTool

import os, sys
import json
import PySide
from PySide.QtGui import QDialog, QApplication, QFileDialog
from ui_SceneTools import Ui_Dialog
import csheet
import sync

version = 0.2

class Config(object):
    config = {'NUKE': r'C:\Program Files\Nuke10.0v4\Nuke10.0.exe', 'SERVER': r'\\192.168.1.7\z', 'PROJECT': 'SNJYW', 'IMAGE_FOLDER': r'Comp\image', 'VIDEO_FOLDER': r'Comp\mov', 'EP': None, 'SCENE': None, 'isImageUp': 2, 'isImageDown': 2, 'isVideoUp': 2, 'isVideoDown': 0, 'isCsheetUp': 2}
    cfgfile_path = os.path.join(os.path.dirname(__file__), 'SceneTools.json')

    def __init__(self):
        self.readConfig()            
        self.updateConfig()
            
    def updateConfig(self):
        with open(self.cfgfile_path, 'w') as file:
            json.dump(self.config, file, indent=4, sort_keys=True)
    
    def readConfig(self):
        if os.path.exists(self.cfgfile_path):
            with open(self.cfgfile_path) as file:
                last_config = file.read()
            if last_config:
                self.config.update(json.loads(last_config))

    def editConfig(self, key, value):
        print(u'设置{}: {}'.format(key, value))
        self.config[key] = value
        self.updateConfig()

class Dialog(QDialog, Ui_Dialog, Config):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        Config.__init__(self)
        self.setupUi(self)

        self.edits_key = {self.nukeEdit: 'NUKE', self.serverEdit: 'SERVER', self.projectEdit: 'PROJECT', self.epEdit: 'EP', self.scEdit: 'SCENE', self.imageUp_check: 'isImageUp', self.imageDown_check: 'isImageDown', self.videoUp_check: 'isVideoUp', self.videoDown_check: 'isVideoDown', self.csheetUp_check: 'isCsheetUp'}
        self.update()

        self.sheetButton.clicked.connect(self.createCsheet)
        self.nukeButton.clicked.connect(self.selectNuke)

        self.connectEdits()    
    
    def update(self):
        for q, k in self.edits_key.iteritems():
            try:
                edit_type = str(type(q))
                if edit_type == "<type 'PySide.QtGui.QLineEdit'>":
                    q.setText(self.config[k])
                if edit_type == "<type 'PySide.QtGui.QCheckBox'>":
                    q.setCheckState(PySide.QtCore.Qt.CheckState(self.config[k]))
            except KeyError as e:
                print(e)
        self.updateConfig()

    def createCsheet(self):
        csheet.main(self.config)
    
    def syncFiles(self):
        sync.main(self.config)
    
    def selectNuke(self):
        fileDialog = QFileDialog()
        fileNames, selectedFilter = fileDialog.getOpenFileName(dir=os.getenv('ProgramFiles'), filter='*.exe')
        if fileNames:
            self.config['NUKE'] = fileNames
            self.update()
            
    def connectEdits(self):
        for edit, key in self.edits_key.iteritems():
            edit_type = str(type(edit))
            if edit_type == "<type 'PySide.QtGui.QLineEdit'>":
                edit.textChanged.connect(lambda text, k=key: self.editConfig(k, text))
            elif edit_type == "<type 'PySide.QtGui.QCheckBox'>":
                edit.stateChanged.connect(lambda state, k=key: self.editConfig(k, state))
            else:
                print(u'待处理的控件: {} {}'.format(edit_type, edit))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    frame = Dialog()
    frame.show()
    sys.exit(app.exec_())
