# -*- coding: UTF-8 -*-

import nuke
import comp
from autolabelCustom import autolabelCustom

comp.addMenu()
nuke.addAutolabel( autolabelCustom )
nuke.addOnCreate(lambda : assetManager.getDropFrameRanges(nuke.thisNode()), nodeClass='Read')
nuke.addOnScriptSave( assetManager.showDropFrames)

nuke.knobDefault( "LayerContactSheet.showLayerNames", "1" )
nuke.knobDefault( "note_font", u"微软雅黑".encode('utf8') )
nuke.knobDefault( "ZDefocus2.blur_dof", "0" )
nuke.knobDefault( "Root.fps", "25" )
nuke.knobDefault( "Root.format", "1920 1080 0 0 1920 1080 1 HD_1080" )
nuke.knobDefault( "Root.project_directory", "[python {nuke.script_directory()}]" )
nuke.knobDefault( "Switch.which", "1" )
nuke.knobDefault( "Viewer.input_process", "False" )
nuke.knobDefault( "SoftClip.conversion", "3" )
