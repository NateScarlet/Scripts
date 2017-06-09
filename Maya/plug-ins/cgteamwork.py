# -*- coding=UTF-8 -*-

from pymel.all import *

SHELF_NAME = 'CgTeamWork'

def initializePlugin( mobject ):
    ''' Initialize the plug-in when Maya loads it. '''
    addShelf()


def uninitializePlugin( mobject ):
    ''' Uninitialize the plug-in when Maya un-loads it. '''
    deleteShelf()


def addShelf():
    deleteShelf()
    setParent('MayaWindow|toolBar2|MainShelfLayout|formLayout14|ShelfLayout')
    shelfLayout(SHELF_NAME)
    shelfButton(annotation=u'Link资产',
        image1="channelBox.png",
        command='import wlf.cgteamwork\nwlf.cgteamwork.CGTeamWork().call_script()',
        imageOverlayLabel=u"联资产",
    )


def deleteShelf():
    shelf = 'MayaWindow|toolBar2|MainShelfLayout|formLayout14|ShelfLayout|' + SHELF_NAME
    if shelfLayout(shelf, exists=True):
        deleteUI(shelf)
