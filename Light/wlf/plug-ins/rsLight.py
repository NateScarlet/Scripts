# -*- coding=UTF-8 -*-
from __future__ import absolute_import

from maya.cmds import setParent, shelfLayout, shelfButton, deleteUI

from _rsLight import rsPhysicalLight, breakAllLightLink


def initializePlugin(mobject):
    ''' Initialize the plug-in when Maya loads it. '''
    addShelf()


def uninitializePlugin(mobject):
    ''' Uninitialize the plug-in when Maya un-loads it. '''
    deleteShelf()


def addShelf():
    deleteShelf()
    setParent('MayaWindow|toolBar2|MainShelfLayout|formLayout14|ShelfLayout')
    shelfLayout('rsLight')
    shelfButton(annotation=u'Redshift物理光',
                image1="light.png",
                command=rsPhysicalLight,
                imageOverlayLabel=u"物理光",
                )

    shelfButton(annotation=u'断开所选灯光所有链接',
                image1='lightBulb.png',
                command=breakAllLightLink,
                imageOverlayLabel=u"断灯光链接")


def deleteShelf():
    shelf = 'MayaWindow|toolBar2|MainShelfLayout|formLayout14|ShelfLayout|rsLight'
    if shelfLayout(shelf, exists=True):
        deleteUI(shelf)
