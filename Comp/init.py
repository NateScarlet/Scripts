# -*- coding: UTF-8 -*-

nuke.pluginAddPath( 'lib' )
nuke.pluginAddPath( 'gizmo' )

import assetManager

nuke.addBeforeRender( assetManager.createOutDirs, nodeClass='Write' )