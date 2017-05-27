# usr/bin/env python
# -*- coding=UTF-8 -*-
# SceneTool
# Version 0.1

import sys

from PySide.QtGui import QDialog, QApplication, QFileDialog
from ui_SceneTools import Ui_Dialog
import contactSheet
from prompt import *

class Dialog(QDialog, Ui_Dialog):
    def __init__(self, parent=None):
        super(Dialog, self).__init__(parent)
        self.setupUi(self)
        self.sheetButton.clicked.connect(self.createContactSheet)
        self.nukeFileButton.clicked.connect(self.selectNukeFile)

        readIni()
        self.nukeFileEdit.setText(ini_dict['NUKE'])

    def createContactSheet(self):
        contactSheet.main()
    
    def selectNukeFile(self):
        fileDialog = QFileDialog()
        ini_dict['NUKE'], ok = fileDialog.getOpenFileName()
        self.nukeFileEdit.setText(ini_dict['NUKE'])
        

if __name__ == '__main__':
    app = QApplication(sys.argv)
    frame = Dialog()
    frame.show()
    sys.exit( app.exec_() )
