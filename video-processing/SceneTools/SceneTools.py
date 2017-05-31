# usr/bin/env python
# -*- coding=UTF-8 -*-
# SceneTool

import os, sys
import PySide.QtCore, PySide.QtGui
from PySide.QtGui import QDialog, QApplication, QFileDialog
from ui_SceneTools import Ui_Dialog
import csheet
import sync
from config import Config

VERSION = 0.2

class Dialog(QDialog, Ui_Dialog, Config):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        Config.__init__(self)
        self.setupUi(self)
        self.version_label.setText('v{}'.format(VERSION))

        self.edits_key = {self.nukeEdit: 'NUKE', self.serverEdit: 'SERVER', self.projectEdit: 'PROJECT', self.epEdit: 'EP', self.scEdit: 'SCENE', self.imageUp_check: 'isImageUp', self.imageDown_check: 'isImageDown', self.videoUp_check: 'isVideoUp', self.videoDown_check: 'isVideoDown', self.csheetUp_check: 'isCsheetUp'}
        self.update()

        self.sheetButton.clicked.connect(self.createCsheet)
        self.nukeButton.clicked.connect(self.selectNuke)

        self.connectEdits()    
    
    def update(self):
        for q, k in self.edits_key.iteritems():
            try:
                if type(q) == PySide.QtGui.QLineEdit:
                    q.setText(self.config[k])
                if type(q) == PySide.QtGui.QCheckBox:
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
            if type(edit) == PySide.QtGui.QLineEdit:
                edit.textChanged.connect(lambda text, k=key: self.editConfig(k, text))
            elif type(edit) == PySide.QtGui.QCheckBox:
                edit.stateChanged.connect(lambda state, k=key: self.editConfig(k, state))
            else:
                print(u'待处理的控件: {} {}'.format(type(edit), edit))

class CommandLineUI(object):
    isUpload = False
    isDownload =False

    EP = None
    IMAGE_FOLDER = None
    NUKE = None
    PROJECT = None
    SCENE = None
    SERVER = None

    image_download_path = None
    image_upload_path = None
    file_name = None
    
    def __init__(self):
        call(u'CHCP 936 & TITLE 生成色板_v{} & CLS'.format(VERSION).encode(prompt_codec), shell=True)
        
    def setStatus(self, choice):
        if choice == 1:
            pass
        elif choice == 2:
            if self.image_upload_path and os.path.exists(os.path.dirname(self.image_upload_path)):
                self.isUpload = True
            else:
                print_('**警告**\t\t图像上传路径不可用, 将不会上传')
        elif choice == 3:
            if self.image_download_path and os.path.exists(self.image_download_path):
                self.isDownload = True
            else:
                print_('**提示**\t\t没有可下载文件')
        elif choice == 4:
            if self.image_upload_path and os.path.exists(os.path.dirname(self.image_upload_path)):
                self.isUpload = True
            else:
                print_('**警告**\t\t图像上传路径不可用, 将不会上传')
            if self.image_download_path and os.path.exists(self.image_download_path):
                self.isDownload = True
            else:
                print_('**提示**\t\t没有可下载文件')
        else:
            exit()
        print('')
        
    def setConfig(self):
        if SERVER and PROJECT and IMAGE_FOLDER:
            self.image_upload_path = '\\'.join([SERVER, PROJECT, IMAGE_FOLDER, time.strftime('%m%d')])
            if EP and SCENE:
                self.image_download_path = '\\'.join([SERVER, PROJECT, IMAGE_FOLDER, EP, SCENE])

        if EP and SCENE:
            self.file_name = 'ContactSheet_{}_{}.jpg'.format(EP, SCENE)
        else:
            self.file_name = 'ContactSheet_{}.jpg'.format(time.strftime('%y%m%d_%H%M'))
        print('')
        
        global file_name
        file_name = self.file_name



if __name__ == '__main__':
    app = QApplication(sys.argv)
    frame = Dialog()
    frame.show()
    sys.exit(app.exec_())
