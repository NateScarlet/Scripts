# -*- coding: UTF-8 -*-

nuke.pluginAddPath( 'lib' )
nuke.pluginAddPath( 'gizmo' )

import assetManager
import comp


nuke.addBeforeRender( assetManager.createOutDirs, nodeClass='Write' )