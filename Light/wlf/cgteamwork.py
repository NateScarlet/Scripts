# -*- coding=UTF-8 -*-

from __future__ import absolute_import
from pymel.all import setParent, shelfLayout, shelfButton, deleteUI

from Lib.cgteamwork import CGTeamWork

SHELF_NAME = 'CgTeamWork'


def initializePlugin(mobject):
    ''' Initialize the plug-in when Maya loads it. '''
    addShelf()


def uninitializePlugin(mobject):
    ''' Uninitialize the plug-in when Maya un-loads it. '''
    deleteShelf()


def addShelf():
    deleteShelf()
    setParent('MayaWindow|toolBar2|MainShelfLayout|formLayout14|ShelfLayout')
    shelfLayout(SHELF_NAME)
    shelfButton(
        annotation=u'Link资产',
        image="",
        command=lambda: CGTeamWork().call_script(),
        imageOverlayLabel=u"联资产",
    )
    shelfButton(
        annotation=u'设置工程',
        image="",
        command=CGTeamWork.show_window,
        imageOverlayLabel=u"设置",
    )


def deleteShelf():
    shelf = 'MayaWindow|toolBar2|MainShelfLayout|formLayout14|ShelfLayout|' + SHELF_NAME
    if shelfLayout(shelf, exists=True):
        deleteUI(shelf)
