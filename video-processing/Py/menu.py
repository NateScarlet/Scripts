# -*- coding: UTF-8 -*-

import nuke
import comp
from autolabelCustom import autolabelCustom

comp.addMenu()
nuke.addAutolabel( autolabelCustom )
nuke.addOnCreate(lambda : assetManager.getDropFrameRanges(nuke.thisNode()), nodeClass='Read')
nuke.addOnScriptSave( assetManager.showDropFrames)
