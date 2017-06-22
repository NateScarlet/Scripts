# -*- coding=UTF-8 -*-
import os

import nuke

import asset
import autocomp
import cgtw
import comp
import csheet
import pref
import callback
import ui
import backdrop

__all__ = ['asset', 'autocomp', 'cgtw', 'comp', 'csheet']

def init():
    callback.add_callback()
    pref.set_knob_default()
    os.environ['NUKE_FONT_PATH'] = '//SERVER/scripts/NukePlugins/Fonts'

def menu():
    ui.add_menu()
    nuke.addAutolabel(ui.custom_autolabel)
    def ttt():
        import tabtabtab
        m_edit = nuke.menu('Nuke').findItem('Edit')
        m_edit.addCommand('Tabtabtab', tabtabtab.main, 'Tab')

    ttt()
