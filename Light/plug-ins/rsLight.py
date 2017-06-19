# -*- coding=UTF-8 -*-

from pymel.all import *


def initializePlugin( mobject ):
    ''' Initialize the plug-in when Maya loads it. '''
    addShelf()


def uninitializePlugin( mobject ):
    ''' Uninitialize the plug-in when Maya un-loads it. '''
    deleteShelf()


def addShelf():
    deleteShelf()
    setParent('MayaWindow|toolBar2|MainShelfLayout|formLayout14|ShelfLayout')
    shelfLayout('rsLight')
    shelfButton(annotation=u'Redshift物理光',
        image1="light.png",
        command='import wlf.light\nwlf.light.rsPhysicalLight()',
        imageOverlayLabel=u"物理光",
    )
    shelfButton(annotation=u'断开所选灯光所有链接',
        image1= 'lightBulb.png',
        command='import wlf.light\nwlf.light.breakAllLightLink()',
        imageOverlayLabel=u"断灯光链接",
        flat  = True,
    )


def deleteShelf():
    shelf = 'MayaWindow|toolBar2|MainShelfLayout|formLayout14|ShelfLayout|rsLight'
    if shelfLayout(shelf, exists=True):
        deleteUI(shelf)
