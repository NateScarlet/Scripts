# usr/bin/env python
# -*- coding=UTF-8 -*-

import os, sys
import re
import locale

from subprocess import call
import PySide.QtCore, PySide.QtGui
from PySide.QtGui import QDialog, QApplication, QFileDialog
from ui_SceneTools import Ui_Dialog

from config import Config
from sync import Sync

VERSION = 0.411

sys_codec = locale.getdefaultlocale()[1]
script_codec = 'UTF-8'

def pause():
    call('PAUSE', shell=True)

class CSheet(Config):
    def createCSheet(self):
        cfg = self.config
        script = os.path.join(os.path.dirname(unicode(sys.argv[0], sys_codec)), 'csheet.py')

        cmd = u'"{NUKE}" -t "{script}"'.format(NUKE=cfg['NUKE'], script=script)
        print(cmd)
        call(cmd.encode(sys_codec))

    def openCSheet(self):
        csheet = self.config['csheet']
        if os.path.exists(self.config['csheet']):
            cmd = u'EXPLORER "{}"'.format(csheet)
            cmd = unicode(cmd).encode(sys_codec)
            call(cmd)
        
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
                            self.backDropBox: 'backdrop_name'
                         }
        self.initBackdrop()
        self.update()

        self.connectButtons()
        self.connectEdits()
        
    
    def connectButtons(self):
        self.nukeButton.clicked.connect(self.execNukeBt)
        self.sheetButton.clicked.connect(self.execCSheetBt)
        self.openCSheetButton.clicked.connect(self.execOpenCSheetBt)
        self.syncButton.clicked.connect(self.execSyncBt)
        self.dirButton.clicked.connect(self.execDirBt)
        self.serverButton.clicked.connect(self.execServerBt)

    def connectEdits(self):
        self.epEdit.textChanged.connect(lambda text: self.setDirByConfig(text, self.config['EP']))
        self.scEdit.textChanged.connect(lambda text: self.setDirByConfig(text, self.config['SCENE']))

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
        dir = self.config['DIR']
        if os.path.exists(dir):
            os.chdir(dir)

        for q, k in self.edits_key.iteritems():
            try:
                if type(q) == PySide.QtGui.QLineEdit:
                    q.setText(self.config[k])
                if type(q) == PySide.QtGui.QCheckBox:
                    q.setCheckState(PySide.QtCore.Qt.CheckState(self.config[k]))
            except KeyError as e:
                print(e)

        self.updateConfig()
        self.setBtEnabled()
        self.updateList()
        
    def setBtEnabled(self):
        dir = self.config['DIR']
        if os.path.exists(dir):
            os.chdir(dir)
            self.sheetButton.setEnabled(True)
            self.syncButton.setEnabled(True)
        else:
            self.sheetButton.setEnabled(False)
            self.syncButton.setEnabled(False)

        if os.path.exists(self.config['csheet']):
            self.openCSheetButton.setEnabled(True)
        else:
            self.openCSheetButton.setEnabled(False)
    
    def execNukeBt(self):
        fileDialog = QFileDialog()
        fileNames, selectedFilter = fileDialog.getOpenFileName(dir=os.getenv('ProgramFiles'), filter='*.exe')
        if fileNames:
            self.config['NUKE'] = fileNames
            self.update()

    def execNukeBt(self):
        fileDialog = QFileDialog()
        fileNames, selectedFilter = fileDialog.getOpenFileName(dir=os.getenv('ProgramFiles'), filter='*.exe')
        if fileNames:
            self.config['NUKE'] = fileNames
            self.update()

    def updateList(self):
        list = self.listWidget
        cfg = self.config

        self.getFileList()
        list.clear()
        for i in (cfg['image_list'] if cfg['isImageUp'] else []) + (cfg['video_list'] if cfg['isVideoUp'] else []):
            list.addItem(u'将上传: {}'.format(i))
        for i in cfg['ignore_list']:
            list.addItem(u'无需上传: {}'.format(i))
            
    def initBackdrop(self):
        self.config['BACKDROP_DIR'] = unicode(os.path.join(os.path.dirname(unicode(sys.argv[0], sys_codec)), u'Backdrops'))
        dir = self.config['BACKDROP_DIR']
        box = self.backDropBox
        if not os.path.exists(dir):
            os.mkdir(dir)
        bd_list = os.listdir(dir)
        for item in bd_list:
            box.addItem(item)
        self.config['backdrop_name'] = box.currentText()
        
    def execCSheetBt(self):
        csheet = self.config['csheet']
        self.createCSheet()
        if self.config['isCSheetOpen']:
            self.openCSheet()
        if self.config['isCSheetUp']:
            self.uploadCSheet()
        self.update()

    def execOpenCSheetBt(self):
        self.openCSheet()
    
    def execDirBt(self):
        fileDialog = QFileDialog()
        dir = fileDialog.getExistingDirectory(dir=os.path.dirname(self.config['DIR']))
        if dir:
            self.config['DIR'] = dir
            self.setConfigByDir()
            self.update()

    def execServerBt(self):
        fileDialog = QFileDialog()
        dir = fileDialog.getExistingDirectory(dir=os.path.dirname(self.config['SERVER']))
        if dir:
            self.config['SERVER'] = dir
            self.update()
      
    def execSyncBt(self):
        cfg = self.config
        if cfg['isImageDown']:
            self.downloadImages()
        if cfg['isImageUp']:
            self.uploadImages()
        if cfg['isVideoUp']:
            self.uploadVideos()
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
    call(u'CHCP 936 & TITLE SceneTools_v{} & CLS'.format(VERSION).encode('GBK'), shell=True)
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