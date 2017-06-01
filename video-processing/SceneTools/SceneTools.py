# usr/bin/env python
# -*- coding=UTF-8 -*-

import os, sys
import re

from subprocess import call
from config import Config
from sync import Sync
import PySide.QtCore, PySide.QtGui
from PySide.QtGui import QDialog, QApplication, QFileDialog
from ui_SceneTools import Ui_Dialog
VERSION = 0.3

def pause():
    call('PAUSE', shell=True)

class CSheet(Config):
    def createCSheet(self):
        cfg = self.config
        script = os.path.join(os.path.dirname(__file__), 'csheet.py')

        cmd = '"{NUKE}" -t "{script}"'.format(NUKE=cfg['NUKE'], script=script)
        print(cmd)
        call(cmd)

    def openCSheet(self):
        csheet = self.config['csheet']
        if os.path.exists(self.config['csheet']):
            call(u'EXPLORER "{}"'.format(csheet))
        
class Dialog(QDialog, Ui_Dialog, CSheet, Sync, Config):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        Config.__init__(self)
        self.setupUi(self)
        self.version_label.setText('v{}'.format(VERSION))

        self.edits_key = {
                            self.serverEdit: 'SERVER', 
                            self.videoFolderEdit: 'SVIDEO_FOLDER', 
                            self.imageFolderEdit: 'SIMAGE_FOLDER', 
                            self.nukeEdit: 'NUKE', 
                            self.dirEdit: 'DIR', 
                            self.projectEdit: 'PROJECT', 
                            self.epEdit: 'EP', 
                            self.scEdit: 'SCENE', 
                            self.csheetFFNameEdit: 'CSHEET_FFNAME', 
                            self.csheetPrefixEdit: 'CSHEET_PREFIX', 
                            self.imageFNameEdit: 'IMAGE_FNAME', 
                            self.videoFNameEdit: 'VIDEO_FNAME', 
                            self.videoDestEdit: 'video_dest', 
                            self.imageDestEdit: 'image_dest', 
                            self.csheetNameEdit: 'csheet_name', 
                            self.csheetDestEdit: 'csheet_dest',
                            self.imageUpCheck: 'isImageUp', 
                            self.imageDownCheck: 'isImageDown', 
                            self.videoUpCheck: 'isVideoUp', 
                            self.videoDownCheck: 'isVideoDown', 
                            self.csheetUpCheck: 'isCSheetUp', 
                            self.csheetOpenCheck: 'isCSheetOpen',
                         }
        self.update()

        self.connectButtons()
        self.connectEdits()
    
    def connectButtons(self):
        self.nukeButton.clicked.connect(self.execNukeBt)
        self.sheetButton.clicked.connect(self.execCSheetBt)
        self.openCSheetButton.clicked.connect(self.execOpenCSheetBt)
        self.syncButton.clicked.connect(self.execSyncBt)
        self.dirButton.clicked.connect(self.execDirBt)

    def connectEdits(self):
        self.epEdit.textChanged.connect(lambda text: self.setDirByConfig(text, self.config['EP']))
        self.scEdit.textChanged.connect(lambda text: self.setDirByConfig(text, self.config['SCENE']))

        for edit, key in self.edits_key.iteritems():
            if type(edit) == PySide.QtGui.QLineEdit:
                edit.textChanged.connect(lambda text, k=key: self.editConfig(k, text))
                edit.textChanged.connect(self.update)
            elif type(edit) == PySide.QtGui.QCheckBox:
                edit.stateChanged.connect(lambda state, k=key: self.editConfig(k, state))
            else:
                print(u'待处理的控件: {} {}'.format(type(edit), edit))

    def update(self):
        dir = self.config['DIR']
        if os.path.exists(dir):
            os.chdir(dir)
            self.sheetButton.setEnabled(True)
            self.syncButton.setEnabled(True)
        else:
            self.sheetButton.setEnabled(False)
            self.syncButton.setEnabled(False)

        for q, k in self.edits_key.iteritems():
            try:
                if type(q) == PySide.QtGui.QLineEdit:
                    q.setText(self.config[k])
                if type(q) == PySide.QtGui.QCheckBox:
                    q.setCheckState(PySide.QtCore.Qt.CheckState(self.config[k]))
            except KeyError as e:
                print(e)
        self.updateConfig()
        self.setOpenBtEnabled()
        self.getFileList()
        self.updateList()
        
    def setOpenBtEnabled(self):
        if os.path.exists(self.config['csheet']):
            self.openCSheetButton.setEnabled(True)
        else:
            self.openCSheetButton.setEnabled(False)

    def syncFiles(self):
        sync.main(self.config)
    
    def execNukeBt(self):
        fileDialog = QFileDialog()
        fileNames, selectedFilter = fileDialog.getOpenFileName(dir=os.getenv('ProgramFiles'), filter='*.exe')
        if fileNames:
            self.config['NUKE'] = fileNames
            self.update()
            
    def updateList(self):
        list = self.listWidget
        cfg = self.config
        list.clear()
        for item in cfg['image_list'] + cfg['video_list']:
            list.addItem(u'将上传: {}'.format(item))
        
    def execCSheetBt(self):
        list = self.listWidget
        csheet = self.config['csheet']

        list.clear()
        self.createCSheet()
        list.addItem(csheet)
        if os.path.exists(csheet):
            self.openCSheetButton.setEnabled(True)
        if self.config['isCSheetOpen']:
            self.openCSheet()

    def execOpenCSheetBt(self):
        call('EXPLORER "{}"'. format(self.config['csheet']))
    
    def execDirBt(self):
        fileDialog = QFileDialog()
        dir = fileDialog.getExistingDirectory(dir=os.path.dirname(self.config['DIR']))
        if dir:
            self.config['DIR'] = dir
            self.setConfigByDir()
            self.update()
        
    def setDirByConfig(self, text, config):
        cfg = self.config
        dir = os.path.normcase(cfg['DIR'] + '\\')
        config = '\\{}\\'.format(os.path.normcase(config))
        if config in dir:
            cfg['DIR'] = dir.replace(config, '\\{}\\'.format(text))[:-1]
                
    def setConfigByDir(self):
        cfg = self.config
        pat = re.compile(r'.*\\(ep.*?)\\.*\\(.+)', flags=re.I)
        match = pat.match(cfg['DIR'])
        if match:
            cfg['EP'], cfg['SCENE'] = match.groups()

def main():
    call(u'CHCP 936 & TITLE 场集工具_v{} & CLS'.format(VERSION).encode('GBK'), shell=True)
    app = QApplication(sys.argv)
    frame = Dialog()
    frame.show()
    sys.exit(app.exec_())
  
if __name__ == '__main__':
    try:
        main()
    except SystemExit as e:
        exit(e)
    except:
        import traceback
        traceback.print_exc()