# -*- coding: UTF-8 -*-

import nuke
from autolabelCustom import autolabelCustom

import comp
import autoComper_WLF
import cgteamwork
import csheet

nuke.pluginAddPath( 'icons' )

# Set menu
comp.addMenu()
autoComper_WLF.addMenu()
cgteamwork.addMenu()
cgteamwork.addCallBack()
# Custom autolabel
nuke.addAutolabel( autolabelCustom )

# Add dropframe check
dropframe_check = assetManager.DropFrameCheck()
dropframe_check.addCallBack()
dropframe_check.addMenu()

#
nuke.addOnScriptSave(comp.enableRSMB, kwargs={'prefix': '_'})

nuke.addOnScriptClose(assetManager.sentToRenderDir)
nuke.addOnScriptClose(csheet.create_csheet)

# Set knob Default
nuke.knobDefault( "LayerContactSheet.showLayerNames", "1" )
nuke.knobDefault( "note_font", u"微软雅黑".encode('utf8') )
nuke.knobDefault( "ZDefocus2.blur_dof", "0" )
nuke.knobDefault( "Root.fps", "25" )
nuke.knobDefault( "Root.format", "1920 1080 0 0 1920 1080 1 HD_1080" )
nuke.knobDefault( "Root.project_directory", "[python {nuke.script_directory()}]" )
nuke.knobDefault( "Switch.which", "1" )
nuke.knobDefault( "Viewer.input_process", "False" )
nuke.knobDefault( "SoftClip.conversion", "3" )
nuke.knobDefault( "RolloffContrast.soft_clip", "1" )
nuke.knobDefault( "ZDefocus2.math", "depth" )

# Add Drop data callback
assetManager.addDropDataCallBack()

# Scripts from Nukepedia

# Ben Dickson's tabtabtab
def ttt():
    import tabtabtab
    m_edit = nuke.menu('Nuke').findItem('Edit')
    m_edit.addCommand('Tabtabtab', tabtabtab.main, 'Tab')

try:
    ttt()
except Exception:
    import traceback
    traceback.print_exc()
