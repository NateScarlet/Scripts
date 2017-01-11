# -*- coding: UTF-8 -*-

nuke.pluginAddPath( 'lib' )

import assetManager
import comp

nuke.addBeforeRender( assetManager.createOutDirs, nodeClass='Write' )