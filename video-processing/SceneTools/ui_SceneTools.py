# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'D:\Users\zhouxuan.WLF\CloudSync\Scripts\video-processing\SceneTools\SceneTools.ui'
#
# Created: Sat May 27 18:30:49 2017
#      by: pyside-uic 0.2.15 running on PySide 1.2.4
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(433, 300)
        self.sheetButton = QtGui.QPushButton(Dialog)
        self.sheetButton.setGeometry(QtCore.QRect(30, 220, 131, 51))
        self.sheetButton.setIconSize(QtCore.QSize(16, 16))
        self.sheetButton.setObjectName("sheetButton")
        self.groupBox = QtGui.QGroupBox(Dialog)
        self.groupBox.setGeometry(QtCore.QRect(40, 20, 351, 121))
        self.groupBox.setLocale(QtCore.QLocale(QtCore.QLocale.Chinese, QtCore.QLocale.China))
        self.groupBox.setObjectName("groupBox")
        self.widget = QtGui.QWidget(self.groupBox)
        self.widget.setGeometry(QtCore.QRect(20, 60, 309, 42))
        self.widget.setObjectName("widget")
        self.verticalLayout = QtGui.QVBoxLayout(self.widget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label_3 = QtGui.QLabel(self.widget)
        self.label_3.setObjectName("label_3")
        self.verticalLayout.addWidget(self.label_3)
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.nukeFileEdit = QtGui.QLineEdit(self.widget)
        self.nukeFileEdit.setDragEnabled(True)
        self.nukeFileEdit.setObjectName("nukeFileEdit")
        self.horizontalLayout_2.addWidget(self.nukeFileEdit)
        self.nukeFileButton = QtGui.QToolButton(self.widget)
        self.nukeFileButton.setObjectName("nukeFileButton")
        self.horizontalLayout_2.addWidget(self.nukeFileButton)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.lineEdit_3 = QtGui.QLineEdit(self.groupBox)
        self.lineEdit_3.setGeometry(QtCore.QRect(20, 20, 158, 20))
        self.lineEdit_3.setObjectName("lineEdit_3")
        self.widget1 = QtGui.QWidget(self.groupBox)
        self.widget1.setGeometry(QtCore.QRect(210, 20, 111, 22))
        self.widget1.setObjectName("widget1")
        self.horizontalLayout = QtGui.QHBoxLayout(self.widget1)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.lineEdit = QtGui.QLineEdit(self.widget1)
        self.lineEdit.setObjectName("lineEdit")
        self.horizontalLayout.addWidget(self.lineEdit)
        self.label = QtGui.QLabel(self.widget1)
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        self.lineEdit_2 = QtGui.QLineEdit(self.widget1)
        self.lineEdit_2.setObjectName("lineEdit_2")
        self.horizontalLayout.addWidget(self.lineEdit_2)
        self.label_2 = QtGui.QLabel(self.widget1)
        self.label_2.setObjectName("label_2")
        self.horizontalLayout.addWidget(self.label_2)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QtGui.QApplication.translate("Dialog", "Dialog", None, QtGui.QApplication.UnicodeUTF8))
        self.sheetButton.setText(QtGui.QApplication.translate("Dialog", "创建色板", None, QtGui.QApplication.UnicodeUTF8))
        self.groupBox.setTitle(QtGui.QApplication.translate("Dialog", "设置", None, QtGui.QApplication.UnicodeUTF8))
        self.label_3.setText(QtGui.QApplication.translate("Dialog", "Nuke路径", None, QtGui.QApplication.UnicodeUTF8))
        self.nukeFileButton.setText(QtGui.QApplication.translate("Dialog", "浏览", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("Dialog", "集", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText(QtGui.QApplication.translate("Dialog", "场", None, QtGui.QApplication.UnicodeUTF8))

